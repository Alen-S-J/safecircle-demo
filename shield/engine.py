"""
Channel-agnostic core facade.

The local demo UI and (later) WhatsApp webhook call these functions.
New logic lives in orchestrator.py; this module keeps the public API stable.
"""
from __future__ import annotations

from . import extract, llm, replies, rules, store
from . import orchestrator
from .policy import POLICY_VERSION, severity_to_risk

REVIEW_CONFIDENCE = 0.6


def analyse(text: str, image_b64: str = None, image_type: str = "image/jpeg", use_ai: bool = True):
    """Pure analysis helper used by eval.py. Uses rules (+ optional legacy classify)."""
    ai_result = None
    ai_on = use_ai and llm.available()

    if image_b64:
        if not ai_on:
            return {"status": "needs_ai"}
        ai_result = llm.classify(text=text, image_b64=image_b64, image_type=image_type)
        if ai_result is None:
            return {"status": "ai_failed"}
        text = "\n".join(t for t in [text, ai_result["extracted_text"]] if t).strip()

    entities = extract.extract(text)
    signals = rules.detect_signals(text) | extract.entity_signals(entities)
    if store.any_reported(extract.entity_keys(entities)):
        signals.add("known_reported")

    rule_risk, rule_category = rules.apply_playbooks(signals)

    if ai_on and ai_result is None and text:
        ai_result = llm.classify(text=text)

    risk, category, needs_review = rule_risk, rule_category, False
    if ai_result:
        signals |= set(ai_result["signals"])
        combined_risk, combined_category = rules.apply_playbooks(signals)
        if rules.RISK_ORDER[combined_risk] > rules.RISK_ORDER[risk]:
            risk, category = combined_risk, combined_category
        ai_risk = ai_result["risk"]
        if rules.RISK_ORDER[ai_risk] > rules.RISK_ORDER[risk]:
            if ai_result["confidence"] >= REVIEW_CONFIDENCE:
                risk = ai_risk
            else:
                risk = "medium" if risk == "low" else risk
                needs_review = True
            if category in ("none", "generic"):
                category = ai_result["category"]
        if risk == "high" and category in ("none", "generic"):
            category = ai_result["category"] if ai_result["category"] not in ("none",) else "generic"

    if risk != "low" and category == "none":
        category = "generic"
    if risk == "high" and rule_risk != "high" and not ai_result:
        needs_review = True

    stage = rules.detect_stage(text, role="other")
    return {
        "status": "ok",
        "text": text,
        "risk": risk,
        "category": category,
        "signals": signals,
        "entities": entities,
        "ai_used": bool(ai_result),
        "ai_note": ai_result["note"] if ai_result else "",
        "needs_review": needs_review,
        "stage": stage,
        "severity": {"high": "high", "medium": "medium", "low": "none"}.get(risk, "none"),
    }


def check(
    text: str = "",
    image_b64: str = None,
    image_type: str = "image/jpeg",
    lang: str = "en",
    use_ai: bool = True,
    case_id: int = None,
    role: str = "other",
):
    return orchestrator.handle_item(
        text=text,
        image_b64=image_b64,
        image_type=image_type,
        lang=lang,
        case_id=case_id,
        role=role,
        use_ai=use_ai,
    )


def ask_family(case_id: int, lang: str = "en"):
    lang = replies.lang_or_default(lang)
    case = store.get_case(case_id)
    if not case:
        return {"status": "not_found"}
    settings = store.get_settings()
    if not settings.get("guardian_name"):
        return {"status": "ok", "message": replies.MESSAGES["no_guardian"][lang]}
    store.mark_case(case_id, "asked_family")
    store.add_alert(case_id, "asked")
    return {
        "status": "ok",
        "message": replies.MESSAGES["asked_family"][lang].format(guardian=settings["guardian_name"]),
    }


def report(case_id: int, lang: str = "en"):
    lang = replies.lang_or_default(lang)
    case = store.get_case(case_id)
    if not case:
        return {"status": "not_found"}
    store.mark_case(case_id, "reported")
    store.report_entities(extract.entity_keys(case["entities"]))
    return {"status": "ok", "message": replies.MESSAGES["reported"][lang]}


def advice(case_id: int, lang: str = "en"):
    case = store.get_case(case_id)
    if not case:
        return {"status": "not_found"}
    return {
        "status": "ok",
        "steps": replies.advice(
            case["risk"], case["category"], lang, _all_signals(case), severity=case.get("severity")
        ),
        "recovery": replies.recovery(lang) if case.get("stage") == "loss" or case.get("severity") == "critical" else None,
    }


def _all_signals(case):
    return set(case["signals"]) | extract.entity_signals(case["entities"])


def _visible(case, level):
    if level == "full":
        return True
    sev = case.get("severity") or ""
    risk = case["risk"]
    if level == "auto_red":
        return bool(case["asked_family"]) or risk == "high" or sev in ("high", "critical")
    return bool(case["asked_family"])


def _masked_entities(entities):
    return {
        "phones": [extract.mask(p, "phone") for p in entities.get("phones", [])],
        "upi_ids": [extract.mask(u, "upi") for u in entities.get("upi_ids", [])],
        "hosts": sorted({l["host"] for l in entities.get("links", []) if l.get("host")}),
    }


def guardian_view():
    import time
    # Process due timers on each poll (no background thread).
    orchestrator.tick()
    settings = store.get_settings()
    level = settings["sharing_level"]
    week_ago = time.time() - 7 * 86400
    cases = store.list_cases()
    week = [c for c in cases if c["created"] >= week_ago]

    def summarise(c):
        return {
            "id": c["id"],
            "created": c["created"],
            "risk": c["risk"],
            "severity": c.get("severity") or severity_to_risk(c.get("severity") or "none") and c.get("severity") or "none",
            "stage": c.get("stage") or "contact",
            "category": c["category"],
            "category_name": replies.CATEGORY_NAMES.get(c["category"], "Unusual message"),
            "signals": [replies.signal_label(s, "en") for s in replies.SIGNAL_PRIORITY if s in c["signals"]],
            "entities": _masked_entities(c["entities"]),
            "asked_family": bool(c["asked_family"]),
            "reported": bool(c["reported"]),
            "review_flag": bool(c.get("review_flag") or c.get("needs_review")),
            "text": c["text"] if level == "full" else None,
            "input_type": c["input_type"],
            "lang": c["lang"],
            "scam_probability": c.get("scam_probability") or 0,
        }

    by_id = {c["id"]: c for c in cases}
    alerts = []
    for a in store.list_alerts():
        c = by_id.get(a["case_id"])
        if c and (_visible(c, level) or a["reason"] == "asked"):
            alerts.append({**a, "case": summarise(c)})

    return {
        "settings": settings,
        "stats": {
            "checked_week": len(week),
            "high_week": sum(1 for c in week if c["risk"] == "high" or c.get("severity") in ("high", "critical")),
            "asked_week": sum(1 for c in week if c["asked_family"]),
            "critical_week": sum(1 for c in week if c.get("severity") == "critical"),
        },
        "alerts": alerts,
        "cases": [summarise(c) for c in cases if _visible(c, level)][:50],
        "policy_version": POLICY_VERSION,
    }


def draft_reply(case_id: int, threat_history: list, lang: str = "en"):
    """v2 Reply Assistant — returns structured drafts (or None)."""
    return orchestrator.drafts(case_id, history=threat_history, lang=lang)


def agent_engage(case_id: int, threat_history: list, lang: str = "en"):
    """Demo takeover — validated reply text or None."""
    return orchestrator.engage(case_id, history=threat_history, lang=lang)


def case_detail(case_id: int):
    return orchestrator.case_detail(case_id)


def override(case_id: int, reviewer: str, verdict: str, note: str = ""):
    return orchestrator.override(case_id, reviewer, verdict, note)
