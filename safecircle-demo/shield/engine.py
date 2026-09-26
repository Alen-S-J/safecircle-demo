"""
The channel-agnostic core. The local demo UI calls these functions today;
the WhatsApp webhook worker will call exactly the same functions later.

    check(text, image, lang)  -> verdict + reply
    ask_family(case_id, lang) -> confirmation
    report(case_id, lang)     -> confirmation
    advice(case_id, lang)     -> step list
"""
from . import extract, llm, replies, rules, store

REVIEW_CONFIDENCE = 0.6


def analyse(text: str, image_b64: str = None, image_type: str = "image/jpeg", use_ai: bool = True):
    """Pure analysis, no storage. Returns a dict describing the verdict."""
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
        # The LLM may add signals and raise risk, but can never lower a rule floor.
        signals |= set(ai_result["signals"])
        combined_risk, combined_category = rules.apply_playbooks(signals)
        if rules.RISK_ORDER[combined_risk] > rules.RISK_ORDER[risk]:
            risk, category = combined_risk, combined_category
        ai_risk = ai_result["risk"]
        if rules.RISK_ORDER[ai_risk] > rules.RISK_ORDER[risk]:
            if ai_result["confidence"] >= REVIEW_CONFIDENCE:
                risk = ai_risk
            else:
                # Low-confidence escalation becomes amber plus human review, never green.
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
    }


def check(text: str = "", image_b64: str = None, image_type: str = "image/jpeg", lang: str = "en", use_ai: bool = True):
    lang = replies.lang_or_default(lang)
    text = (text or "").strip()[:5000]
    if not text and not image_b64:
        return {"status": "empty", "message": replies.MESSAGES["empty"][lang]}

    result = analyse(text, image_b64, image_type, use_ai)
    if result["status"] == "needs_ai":
        return {"status": "needs_ai", "message": replies.MESSAGES["needs_ai"][lang]}
    if result["status"] == "ai_failed":
        return {"status": "ai_failed", "message": replies.MESSAGES["needs_ai"][lang]}

    case_id = store.save_case(
        lang=lang, input_type="image" if image_b64 else "text", text=result["text"],
        risk=result["risk"], category=result["category"], signals=result["signals"],
        entities=result["entities"], ai_used=result["ai_used"], ai_note=result["ai_note"],
        needs_review=result["needs_review"],
    )

    settings = store.get_settings()
    auto_alerted = False
    if result["risk"] == "high" and settings["sharing_level"] in ("auto_red", "full"):
        store.add_alert(case_id, "auto_high")
        auto_alerted = True

    reply = replies.compose(result["risk"], result["category"], result["signals"], lang)
    return {
        "status": "ok",
        "case_id": case_id,
        "risk": result["risk"],
        "category": result["category"],
        "category_name": replies.CATEGORY_NAMES.get(result["category"], "Unusual message"),
        "signals": sorted(s for s in result["signals"] if s not in rules.INTERNAL_SIGNALS),
        "ai_used": result["ai_used"],
        "needs_review": result["needs_review"],
        "auto_alerted": auto_alerted,
        "reply": reply,
    }


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
    return {"status": "ok", "message": replies.MESSAGES["asked_family"][lang].format(guardian=settings["guardian_name"])}


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
    return {"status": "ok", "steps": replies.advice(case["risk"], case["category"], lang, _all_signals(case))}


def _all_signals(case):
    """Stored signals plus entity-derived internal ones (e.g. has_link)."""
    return set(case["signals"]) | extract.entity_signals(case["entities"])


# ---------- Family dashboard ----------

def _visible(case, level):
    if level == "full":
        return True
    if level == "auto_red":
        return bool(case["asked_family"]) or case["risk"] == "high"
    return bool(case["asked_family"])


def _masked_entities(entities):
    return {
        "phones": [extract.mask(p, "phone") for p in entities.get("phones", [])],
        "upi_ids": [extract.mask(u, "upi") for u in entities.get("upi_ids", [])],
        "hosts": sorted({l["host"] for l in entities.get("links", []) if l.get("host")}),
    }


def guardian_view():
    import time
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
            "category": c["category"],
            "category_name": replies.CATEGORY_NAMES.get(c["category"], "Unusual message"),
            "signals": [replies.signal_label(s, "en") for s in replies.SIGNAL_PRIORITY if s in c["signals"]],
            "entities": _masked_entities(c["entities"]),
            "asked_family": bool(c["asked_family"]),
            "reported": bool(c["reported"]),
            "text": c["text"] if level == "full" else None,
            "input_type": c["input_type"],
            "lang": c["lang"],
        }

    by_id = {c["id"]: c for c in cases}
    alerts = []
    for a in store.list_alerts():
        c = by_id.get(a["case_id"])
        if c and _visible(c, level) or (c and a["reason"] == "asked"):
            alerts.append({**a, "case": summarise(c)})

    return {
        "settings": settings,
        "stats": {
            "checked_week": len(week),
            "high_week": sum(1 for c in week if c["risk"] == "high"),
            "asked_week": sum(1 for c in week if c["asked_family"]),
        },
        "alerts": alerts,
        "cases": [summarise(c) for c in cases if _visible(c, level)][:50],
    }
