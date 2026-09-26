"""
Deterministic orchestrator: models advise, code decides.

Implements the v2 main loop: rules → ML → detection → facts → severity →
judge (on triggers) → elder templates → family alerts → audit.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from . import extract, llm, replies, rules, store
from .agents import detection as det_agent
from .agents import judge as judge_agent
from .agents import reply_assistant, takeover
from .policy import (
    EMERGENCY_SECONDS,
    NUDGE_SECONDS,
    POLICY_VERSION,
    family_alert_reason,
    imminence as compute_imminence,
    max_severity,
    max_stage,
    needs_probability_review,
    probability_floor,
    severity as compute_severity,
    severity_to_risk,
    should_offer_reply_assistant,
)


def _ml_predict(text: str) -> Optional[dict]:
    try:
        from . import ml_layer
        return ml_layer.predict(text)
    except Exception as exc:
        print(f"[ml] predict failed: {exc}")
        return None


def _merge_entities(base: dict, extra: dict | None) -> dict:
    out = {
        "links": list(base.get("links") or []),
        "phones": list(base.get("phones") or []),
        "upi_ids": list(base.get("upi_ids") or []),
        "amounts": list(base.get("amounts") or []),
    }
    if not extra:
        return out
    for p in extra.get("phones") or []:
        if p and p not in out["phones"]:
            out["phones"].append(p)
    for u in extra.get("upi_ids") or []:
        if u and u not in out["upi_ids"]:
            out["upi_ids"].append(u)
    for u in extra.get("urls") or []:
        if u:
            out["links"].append(extract.check_link(u))
    return out


def handle_item(
    *,
    text: str = "",
    image_b64: str = None,
    image_type: str = "image/jpeg",
    lang: str = "en",
    case_id: int = None,
    role: str = "other",
    use_ai: bool = True,
) -> dict:
    """
    Main loop for one forwarded / typed item.
    role: 'other' (scammer / unknown) or 'elder' (older person's own words).
    """
    lang = replies.lang_or_default(lang)
    role = "elder" if (role or "").lower() in ("elder", "user", "self") else "other"
    text = (text or "").strip()[:5000]
    trace: list[dict] = []

    if not text and not image_b64:
        return {"status": "empty", "message": replies.MESSAGES["empty"][lang]}

    ai_on = use_ai and llm.available()
    if image_b64 and not ai_on:
        return {"status": "needs_ai", "message": replies.MESSAGES["needs_ai"][lang]}

    # --- create or load case ---
    case = store.get_case(case_id) if case_id else None
    if case is None:
        case_id = store.save_case(
            lang=lang,
            input_type="image" if image_b64 else "text",
            text=text,
            risk="low",
            category="none",
            signals=set(),
            entities={"links": [], "phones": [], "upi_ids": [], "amounts": []},
            ai_used=False,
            stage="contact",
            severity="none",
            imminence="days",
            scam_probability=0,
            policy_version=POLICY_VERSION,
        )
        case = store.get_case(case_id)

    message_id = store.add_item(case_id, role, text or "[image]")
    sev_before = case.get("severity") or "none"

    # --- rules ---
    entities = extract.extract(text)
    signals = rules.detect_signals(text) | extract.entity_signals(entities)
    if store.any_reported(extract.entity_keys(entities)):
        signals.add("known_reported")
    rule_floor, rule_category = rules.apply_playbooks(signals)
    # Map playbook "low" to policy floor language: rules return low|medium|high.
    if rule_floor == "low":
        rule_floor_policy = "low"
    else:
        rule_floor_policy = rule_floor
    rules_stage = rules.detect_stage(text, role=role)
    trace.append({
        "step": "rules",
        "floor": rule_floor_policy,
        "category": rule_category,
        "stage": rules_stage,
        "signals": sorted(s for s in signals if s not in rules.INTERNAL_SIGNALS),
    })

    # --- ML ---
    ml_result = _ml_predict(text) if text else None
    p_ml = float(ml_result["scam_probability"]) if ml_result else None
    if ml_result:
        trace.append({
            "step": "ml",
            "scam_probability": p_ml,
            "p_bert": ml_result.get("p_bert"),
            "p_gnn": ml_result.get("p_gnn"),
            "latency_ms": ml_result.get("latency_ms"),
        })
    else:
        trace.append({"step": "ml", "scam_probability": None, "available": False})

    # --- Detection agent ---
    det = None
    if ai_on:
        facts_so_far = store.list_facts(case_id)
        det = det_agent.run(
            case,
            text,
            rules_signals=signals,
            rules_floor=rule_floor_policy,
            rules_category=rule_category,
            rules_stage=rules_stage,
            entities=entities,
            facts=facts_so_far,
            image_b64=image_b64,
            image_type=image_type,
            message_id=message_id,
        )
        if det is None and image_b64 and not text:
            return {"status": "ai_failed", "message": replies.MESSAGES["needs_ai"][lang]}
        if det and det.get("extracted_text") and not text:
            text = det["extracted_text"]
            # Re-run rules on OCR text.
            entities = extract.extract(text)
            signals = rules.detect_signals(text) | extract.entity_signals(entities)
            rule_floor, rule_category = rules.apply_playbooks(signals)
            rule_floor_policy = rule_floor
            rules_stage = rules.detect_stage(text, role=role)
        if det:
            for s in det.get("signals") or []:
                sid = s["id"] if isinstance(s, dict) else s
                signals.add(sid)
            entities = _merge_entities(entities, det.get("entities"))
            if rule_category in ("none", "generic") and det.get("categories"):
                c0 = det["categories"][0]
                if c0 not in ("benign", "none"):
                    rule_category = c0
            trace.append({
                "step": "detection",
                "scam_probability": det.get("scam_probability"),
                "stage": det.get("stage"),
                "categories": det.get("categories"),
                "signals": [s["id"] if isinstance(s, dict) else s for s in (det.get("signals") or [])],
            })
        else:
            trace.append({"step": "detection", "status": "unavailable_or_invalid"})

    # Probability floors from ML + detection.
    p_det = float(det["scam_probability"]) if det and det.get("scam_probability") is not None else None
    probs = [p for p in (p_ml, p_det) if p is not None]
    scam_probability = max(probs) if probs else 0.0
    model_floor = probability_floor(scam_probability)
    # Combined floor: max of rules + model probability floors.
    floor_order = {"low": 0, "medium": 1, "high": 2}
    combined_floor = rule_floor_policy
    if floor_order.get(model_floor, 0) > floor_order.get(combined_floor, 0):
        combined_floor = model_floor
    # Re-apply playbooks after adding detection signals.
    play_risk, play_cat = rules.apply_playbooks(signals)
    if floor_order.get(play_risk, 0) > floor_order.get(combined_floor, 0):
        combined_floor = play_risk
    if play_cat not in ("none",) and (rule_category in ("none", "generic") or floor_order.get(play_risk, 0) >= floor_order.get(rule_floor_policy, 0)):
        rule_category = play_cat

    # --- facts (append-only) ---
    new_facts: set[str] = set()
    for fact_name, quote in rules.signals_to_facts(signals, text):
        if store.append_fact(case_id, fact_name, source="rules", message_id=message_id, quote=quote):
            new_facts.add(fact_name)
    if role == "elder":
        if rules_stage == "compliance" and store.append_fact(
            case_id, "elder_complied", source="rules", message_id=message_id, quote=text[:120]
        ):
            new_facts.add("elder_complied")
        if rules_stage == "loss" and store.append_fact(
            case_id, "loss_reported", source="rules", message_id=message_id, quote=text[:120]
        ):
            new_facts.add("loss_reported")
    if "ai_manipulation_attempt" in signals:
        # Injection raises floor to at least high.
        if floor_order.get(combined_floor, 0) < floor_order["high"]:
            combined_floor = "high"

    all_facts = store.fact_names(case_id)
    det_stage = det.get("stage") if det else None
    stage = max_stage(case.get("stage") or "contact", rules_stage, det_stage)
    if "loss_reported" in all_facts:
        stage = max_stage(stage, "loss")
    if "elder_complied" in all_facts:
        stage = max_stage(stage, "compliance")

    imm = compute_imminence(stage, all_facts, signals)
    sev = compute_severity(stage, imm, signals, combined_floor)
    sev = max_severity(case.get("severity") or "none", sev)
    # Injection → at least high.
    if "ai_manipulation_attempt" in signals:
        sev = max_severity(sev, "high")

    review_flag = bool(case.get("review_flag"))
    if needs_probability_review(scam_probability, rule_floor_policy):
        review_flag = True
    if det is None and ai_on and text:
        review_flag = True  # invalid/missing model output → flag

    # --- Judge ---
    judge_out = None
    items = store.list_items(case_id)
    if judge_agent.should_trigger(
        {**case, "signals": sorted(signals), "text": text, "severity": sev},
        new_facts=new_facts,
        sev_before=sev_before,
        sev_after=sev,
        det=det,
        rules_floor=rule_floor_policy,
        item_count=len(items),
    ) and ai_on:
        judge_out = judge_agent.run(case={**case, "signals": sorted(signals), "severity": sev, "stage": stage, "category": rule_category},
                                    facts=store.list_facts(case_id), items=items)
        if judge_out:
            sev = max_severity(sev, judge_out.get("recommended_severity") or sev)
            stage = max_stage(stage, judge_out.get("recommended_stage") or stage)
            if judge_out.get("contradictions") or judge_out.get("injection_detected"):
                review_flag = True
            if judge_out.get("verdict") == "likely_genuine":
                review_flag = True  # never clears; human review
            if judge_out.get("categories") and rule_category in ("none", "generic"):
                c0 = judge_out["categories"][0]
                if c0 not in ("benign", "none"):
                    rule_category = c0
            trace.append({
                "step": "judge",
                "verdict": judge_out.get("verdict"),
                "recommended_severity": judge_out.get("recommended_severity"),
                "next_action": judge_out.get("next_action"),
            })
        else:
            trace.append({"step": "judge", "status": "unavailable_or_invalid"})

    if rule_category == "none" and sev != "none":
        rule_category = "generic"
    risk = severity_to_risk(sev)

    # Timers for nudge / emergency.
    now = time.time()
    last_warned = float(case.get("last_warned_at") or 0)
    nudge_due = float(case.get("nudge_due_at") or 0)
    emergency_due = float(case.get("emergency_due_at") or 0)
    if sev in ("high", "critical"):
        last_warned = now
        # Nudge: if elder keeps engaging (another item from same case after warning).
        if len(items) > 1 and sev_before in ("high", "critical"):
            nudge_due = now  # fire re-offer immediately via flag
        if sev == "critical" and emergency_due == 0:
            emergency_due = now + EMERGENCY_SECONDS

    store.update_case(
        case_id,
        text=(case.get("text") or "") and (text if not case.get("text") else case["text"]),
        risk=risk,
        category=rule_category,
        signals=signals,
        entities=entities,
        ai_used=bool(det or ml_result),
        ai_note=(det or {}).get("reviewer_note", "") if det else "",
        needs_review=review_flag,
        review_flag=review_flag,
        stage=stage,
        severity=sev,
        imminence=imm,
        scam_probability=scam_probability,
        policy_version=POLICY_VERSION,
        last_warned_at=last_warned,
        nudge_due_at=nudge_due if sev in ("high", "critical") and len(items) > 1 else case.get("nudge_due_at") or 0,
        emergency_due_at=emergency_due,
    )
    # Prefer latest text for display.
    store.update_case(case_id, text=text or case.get("text") or "")

    case = store.get_case(case_id)
    settings = store.get_settings()
    guardian = settings.get("guardian_name") or "your family"
    emergency_on = settings.get("emergency_alerts", "1") == "1"
    sharing = settings.get("sharing_level", "auto_red")

    # --- family alerts ---
    family_alerted = False
    alert_reason = family_alert_reason(
        sev,
        sharing_level=sharing,
        emergency_alerts=emergency_on,
        asked=False,
        emergency_due=False,
    )
    # For high without emergency: only auto_red/full.
    if alert_reason:
        store.add_alert(case_id, alert_reason)
        family_alerted = True
        trace.append({"step": "family_alert", "reason": alert_reason})

    # Nudge re-warn when continuing after high/critical.
    nudged = False
    if sev in ("high", "critical") and len(items) > 1 and sev_before in ("high", "critical"):
        nudged = True
        trace.append({"step": "nudge", "message": "re-warn after continued engagement"})

    # --- elder-facing reply ---
    reply = replies.compose(risk, rule_category, signals, lang, severity=sev)
    recovery_steps = None
    if "loss_reported" in all_facts or stage == "loss":
        recovery_steps = replies.recovery(lang)
        trace.append({"step": "recovery_script", "steps": recovery_steps})

    elder_notice = None
    if family_alerted:
        elder_notice = replies.family_alerted_message(lang, guardian)
    if nudged:
        elder_notice = (elder_notice + " " if elder_notice else "") + replies.NUDGE_REWARN[lang]

    offer_ra = should_offer_reply_assistant(sev)

    store.add_audit(
        case_id,
        item_id=message_id,
        rules={"floor": combined_floor, "signals": sorted(signals), "category": rule_category, "stage": rules_stage},
        ml=ml_result or {},
        detection=det or {},
        judge=judge_out or {},
        severity_before=sev_before,
        severity_after=sev,
        action="handle_item",
        policy_version=POLICY_VERSION,
    )

    shown_signals = sorted(s for s in signals if s not in rules.INTERNAL_SIGNALS)
    return {
        "status": "ok",
        "case_id": case_id,
        "message_id": message_id,
        "risk": risk,
        "severity": sev,
        "stage": stage,
        "imminence": imm,
        "category": rule_category,
        "category_name": replies.CATEGORY_NAMES.get(rule_category, "Unusual message"),
        "signals": shown_signals,
        "scam_probability": round(scam_probability, 4),
        "ai_used": bool(det),
        "ml": ml_result,
        "needs_review": review_flag,
        "review_flag": review_flag,
        "auto_alerted": family_alerted,
        "family_alerted": family_alerted,
        "family_alert_reason": alert_reason,
        "elder_notice": elder_notice,
        "recovery": recovery_steps,
        "offer_reply_assistant": offer_ra,
        "demo_takeover_allowed": (
            sev in ("high", "critical") and ai_on and llm.demo_takeover_enabled()
        ),
        "reply": reply,
        "trace": trace,
        "policy_version": POLICY_VERSION,
        "new_facts": sorted(new_facts),
    }


def tick() -> list[dict]:
    """Process due nudge / emergency timers. Called from guardian polls."""
    fired = []
    settings = store.get_settings()
    emergency_on = settings.get("emergency_alerts", "1") == "1"
    sharing = settings.get("sharing_level", "auto_red")
    now = time.time()
    for case in store.due_cases(now):
        cid = case["id"]
        sev = case.get("severity") or "none"
        if case.get("emergency_due_at") and case["emergency_due_at"] <= now and emergency_on and sev == "critical":
            # No response within 10 minutes → alert if emergency on.
            store.add_alert(cid, "emergency")
            store.update_case(cid, emergency_due_at=0)
            store.add_audit(cid, action="emergency_timer", severity_before=sev, severity_after=sev,
                            policy_version=POLICY_VERSION)
            fired.append({"case_id": cid, "reason": "emergency"})
        if case.get("nudge_due_at") and case["nudge_due_at"] <= now:
            # Re-offer ask family for ask_only after 10 minutes of high engagement.
            if sharing == "ask_only" and sev in ("high", "critical"):
                store.add_audit(cid, action="nudge_ask_family", severity_before=sev, severity_after=sev,
                                policy_version=POLICY_VERSION)
                fired.append({"case_id": cid, "reason": "nudge"})
            store.update_case(cid, nudge_due_at=0)
    return fired


def override(case_id: int, reviewer: str, verdict: str, note: str = "") -> dict:
    """Human override: may lower severity; facts stay. Always logged."""
    case = store.get_case(case_id)
    if not case:
        return {"status": "not_found"}
    reviewer = (reviewer or "").strip()[:80] or "reviewer"
    note = (note or "").strip()[:400]
    # Map verdict to severity.
    mapping = {
        "none": "none", "low": "none", "medium": "medium", "high": "high",
        "critical": "critical", "likely_genuine": "none", "unclear": case.get("severity") or "none",
        "likely_scam": max_severity(case.get("severity") or "none", "high"),
    }
    new_sev = mapping.get(verdict, verdict if verdict in ("none", "medium", "high", "critical") else case.get("severity"))
    old = case.get("severity") or "none"
    store.update_case(
        case_id,
        severity=new_sev,
        risk=severity_to_risk(new_sev),
        override_by=reviewer,
        override_note=note,
        review_flag=False,
        needs_review=False,
    )
    store.add_audit(
        case_id,
        action="human_override",
        severity_before=old,
        severity_after=new_sev,
        judge={"reviewer": reviewer, "note": note, "verdict": verdict},
        policy_version=POLICY_VERSION,
    )
    return {"status": "ok", "severity": new_sev, "previous": old}


def drafts(case_id: int, history: list = None, lang: str = "en") -> Optional[dict]:
    case = store.get_case(case_id)
    if not case:
        return None
    return reply_assistant.run(case, history=history or [], facts=store.list_facts(case_id), lang=lang)


def engage(case_id: int, history: list = None, lang: str = "en") -> Optional[str]:
    case = store.get_case(case_id)
    if not case:
        return None
    if (case.get("severity") or "none") not in ("high", "critical"):
        return None
    if not llm.demo_takeover_enabled():
        return None
    text = takeover.run(case, history or [], lang=lang)
    if text:
        store.add_audit(
            case_id,
            action="demo_takeover",
            severity_before=case.get("severity"),
            severity_after=case.get("severity"),
            detection={"reply": text[:200]},
            policy_version=POLICY_VERSION,
        )
    return text


def case_detail(case_id: int) -> Optional[dict]:
    case = store.get_case(case_id)
    if not case:
        return None
    return {
        "case": case,
        "items": store.list_items(case_id),
        "facts": store.list_facts(case_id),
        "audit": store.list_audit(case_id),
    }
