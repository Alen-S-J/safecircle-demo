"""Allowed lists and schema validators for agent JSON outputs."""
from __future__ import annotations

from typing import Any, Optional

ALLOWED_SIGNALS = frozenset({
    "otp_request", "money_request", "urgency", "new_number", "family_claim",
    "secrecy", "authority_police", "arrest_threat", "video_call_demand", "parcel",
    "bank_impersonation", "account_threat", "utility_cut", "remote_app", "prize",
    "investment_returns", "job_task", "refund", "emotional_bond", "hardship_story",
    "upi_collect", "suspicious_link", "fake_brand_link", "short_link", "apk_link",
    "documents_request", "ai_manipulation_attempt", "pin_request", "password_request",
    "known_reported",
})

ALLOWED_CATEGORIES = frozenset({
    "family_impersonation", "digital_arrest", "bank_kyc", "otp_theft",
    "upi_collect", "remote_access", "utility_cut", "investment", "job_task",
    "romance", "prize", "refund", "fake_link", "known_reported", "generic", "benign", "none",
})

ALLOWED_STAGES = frozenset({"contact", "hook", "ask", "compliance", "loss"})

ALLOWED_SEVERITIES = frozenset({"none", "medium", "high", "critical"})

ALLOWED_ACTIONS = frozenset({
    "none", "warn_again", "offer_ask_family", "alert_family_now",
    "recovery_script", "suggest_block_and_report", "human_review",
})

ALLOWED_VERDICTS = frozenset({"likely_scam", "unclear", "likely_genuine"})


def _quote_in_text(quote: str, text: str) -> bool:
    if not quote:
        return False
    q = " ".join(str(quote).lower().split())
    t = " ".join(str(text).lower().split())
    if not q:
        return False
    if q in t:
        return True
    # Allow short substring match (≥8 chars) for OCR noise.
    if len(q) >= 8 and q[:8] in t:
        return True
    return False


def validate_detection(raw: Any, source_text: str) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    signals_in = raw.get("signals") or []
    clean_signals = []
    if isinstance(signals_in, list):
        for s in signals_in:
            if isinstance(s, dict):
                sid = s.get("id")
                quote = str(s.get("quote") or "")[:120]
                if sid in ALLOWED_SIGNALS and _quote_in_text(quote, source_text):
                    clean_signals.append({"id": sid, "quote": quote})
                elif sid in ALLOWED_SIGNALS and not quote:
                    # No quote → keep signal id only if the id string appears as a rule-like hint;
                    # still drop invented evidence with fake quotes.
                    continue
            elif isinstance(s, str) and s in ALLOWED_SIGNALS:
                # Bare string signals are accepted only when the signal name is not claimed as evidence.
                # Prefer dropping bare strings that aren't backed — but for robustness keep known ids.
                clean_signals.append({"id": s, "quote": ""})
    # Drop bare-string signals that have empty quotes (invented / unbacked).
    clean_signals = [s for s in clean_signals if s["quote"] or False]
    # Re-add bare ids only when they clearly appear via rule engine — orchestrator merges.
    # Keep quoted ones; also keep unquoted if model listed them and text is empty (image-only).
    if not source_text.strip():
        for s in signals_in:
            if isinstance(s, str) and s in ALLOWED_SIGNALS:
                clean_signals.append({"id": s, "quote": ""})
            elif isinstance(s, dict) and s.get("id") in ALLOWED_SIGNALS:
                clean_signals.append({"id": s["id"], "quote": str(s.get("quote") or "")[:120]})

    cats = [c for c in (raw.get("categories") or []) if c in ALLOWED_CATEGORIES]
    if not cats and raw.get("category") in ALLOWED_CATEGORIES:
        cats = [raw["category"]]
    stage = raw.get("stage") if raw.get("stage") in ALLOWED_STAGES else "contact"
    try:
        p = max(0.0, min(1.0, float(raw.get("scam_probability", 0.5))))
    except (TypeError, ValueError):
        p = 0.5
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    return {
        "schema_version": "det-2.0",
        "extracted_text": str(raw.get("extracted_text") or "")[:4000],
        "sender_shown": str(raw.get("sender_shown") or "")[:120],
        "language": str(raw.get("language") or "en")[:8],
        "categories": cats or ["generic"],
        "stage": stage,
        "signals": clean_signals,
        "entities": {
            "phones": list(entities.get("phones") or [])[:10],
            "upi_ids": list(entities.get("upi_ids") or [])[:10],
            "urls": list(entities.get("urls") or [])[:10],
            "bank_accounts": list(entities.get("bank_accounts") or [])[:10],
            "claimed_identity": str(entities.get("claimed_identity") or "")[:120],
        },
        "scam_probability": p,
        "reviewer_note": str(raw.get("reviewer_note") or "")[:400],
    }


def validate_reply(raw: Any, lang: str = "en") -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    drafts_in = raw.get("drafts") or []
    drafts = []
    if isinstance(drafts_in, list):
        for i, d in enumerate(drafts_in[:3]):
            if not isinstance(d, dict):
                continue
            text = str(d.get("text") or "").strip()
            if not text:
                continue
            drafts.append({
                "id": str(d.get("id") or f"d{i + 1}"),
                "purpose": str(d.get("purpose") or "end")[:40],
                "text": text[:200],
            })
    return {
        "schema_version": "reply-2.0",
        "language": lang,
        "recommend_no_reply": bool(raw.get("recommend_no_reply", True)),
        "drafts": drafts,
    }


def validate_judge(raw: Any, current_severity: str, current_stage: str) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    verdict = raw.get("verdict") if raw.get("verdict") in ALLOWED_VERDICTS else "unclear"
    rec_sev = raw.get("recommended_severity")
    if rec_sev not in ALLOWED_SEVERITIES:
        rec_sev = current_severity
    # Monotonic: never lower.
    from ..policy import SEVERITY_ORDER, STAGE_ORDER, max_severity, max_stage
    if SEVERITY_ORDER.get(rec_sev, 0) < SEVERITY_ORDER.get(current_severity, 0):
        rec_sev = current_severity
    rec_stage = raw.get("recommended_stage")
    if rec_stage not in ALLOWED_STAGES:
        rec_stage = current_stage
    if STAGE_ORDER.get(rec_stage, 0) < STAGE_ORDER.get(current_stage, 0):
        rec_stage = current_stage
    rec_sev = max_severity(current_severity, rec_sev)
    rec_stage = max_stage(current_stage, rec_stage)
    action = raw.get("next_action") if raw.get("next_action") in ALLOWED_ACTIONS else "none"
    cats = [c for c in (raw.get("categories") or []) if c in ALLOWED_CATEGORIES]
    return {
        "schema_version": "judge-2.0",
        "verdict": verdict,
        "recommended_severity": rec_sev,
        "recommended_stage": rec_stage,
        "categories": cats,
        "contradictions": raw.get("contradictions") if isinstance(raw.get("contradictions"), list) else [],
        "trust_building": raw.get("trust_building") if isinstance(raw.get("trust_building"), list) else [],
        "injection_detected": bool(raw.get("injection_detected")),
        "elder_state": str(raw.get("elder_state") or "")[:40],
        "possible_benign_explanation": raw.get("possible_benign_explanation"),
        "verification_that_would_confirm": raw.get("verification_that_would_confirm"),
        "next_action": action,
        "reviewer_note": str(raw.get("reviewer_note") or "")[:400],
    }
