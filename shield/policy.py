"""
Deterministic policy: severity, imminence, stage ordering, escalation matrix.

Models advise; this module (and the orchestrator) decide. Severity never drops
automatically — only a named human override can lower a verdict.
"""
from __future__ import annotations

POLICY_VERSION = "2.0"

STAGES = ("contact", "hook", "ask", "compliance", "loss")
STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}

SEVERITIES = ("none", "medium", "high", "critical")
SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}

IMMINENCE = ("days", "hours", "minutes")
IMMINENCE_ORDER = {s: i for i, s in enumerate(IMMINENCE)}

# Signals that mean a credential / remote-access ask is in play.
CREDENTIAL_ASKS = frozenset({"otp_request", "upi_collect", "remote_app", "apk_link", "pin_request", "password_request"})

NUDGE_SECONDS = 10 * 60
EMERGENCY_SECONDS = 10 * 60

# Rough mapping used for the legacy risk field so older UIs keep working.
SEVERITY_TO_RISK = {
    "critical": "high",
    "high": "high",
    "medium": "medium",
    "none": "low",
}

RISK_TO_FLOOR = {"low": "low", "medium": "medium", "high": "high"}


def max_stage(*stages) -> str:
    best = "contact"
    for s in stages:
        if s in STAGE_ORDER and STAGE_ORDER[s] > STAGE_ORDER[best]:
            best = s
    return best


def max_severity(*sevs) -> str:
    best = "none"
    for s in sevs:
        if s in SEVERITY_ORDER and SEVERITY_ORDER[s] > SEVERITY_ORDER[best]:
            best = s
    return best


def probability_floor(p: float | None) -> str:
    """Map a scam_probability to a rule-style floor contribution."""
    if p is None:
        return "low"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "low"
    if p >= 0.85:
        return "high"
    if p >= 0.5:
        return "medium"
    return "low"


def severity_to_risk(sev: str) -> str:
    return SEVERITY_TO_RISK.get(sev, "low")


def imminence(stage: str, facts: set | frozenset, signals: set | frozenset) -> str:
    """How soon harm could land."""
    facts = set(facts or ())
    signals = set(signals or ())
    if stage in ("compliance", "loss"):
        return "minutes"
    if signals & CREDENTIAL_ASKS or facts & {
        "otp_requested", "pin_requested", "password_requested", "remote_access_requested",
    }:
        return "minutes"
    if ("money_requested" in facts or "fee_requested" in facts or "money_request" in signals) and (
        "urgency" in signals
    ):
        return "minutes"
    if "money_request" in signals or "fee_requested" in facts or "money_requested" in facts:
        return "hours"
    if stage == "hook" and "urgency" in signals:
        return "hours"
    if stage in ("ask", "hook"):
        return "hours"
    return "days"


def severity(stage: str, imm: str, signals: set | frozenset, rule_floor: str) -> str:
    """
    Spec §3 — severity from stage, imminence, signals and rule floor.
    Models never set this directly.

    Note: bare `or signals` in the prose would flag every bank name mention.
    We require an actionable/hook signal set, not empty-or-any.
    """
    signals = set(signals or ())
    rule_floor = rule_floor if rule_floor in ("low", "medium", "high") else "low"
    if stage in ("compliance", "loss"):
        return "critical"
    if stage == "ask" and (signals & CREDENTIAL_ASKS):
        return "critical"
    if stage == "ask" or rule_floor == "high":
        return "high"
    weak_only = signals <= {"bank_impersonation", "has_phone", "has_link", "has_amount", "has_upi"}
    if rule_floor == "medium" or (stage == "hook" and not weak_only) or (signals and not weak_only):
        return "medium"
    if stage == "hook" and signals and not weak_only:
        return "medium"
    return "none"


def should_offer_reply_assistant(sev: str) -> bool:
    return sev in ("medium", "high", "critical")


def family_alert_reason(
    sev: str,
    *,
    sharing_level: str,
    emergency_alerts: bool,
    asked: bool = False,
    emergency_due: bool = False,
) -> str | None:
    """
    Escalation matrix §4. Returns an alert reason or None.
    Elder is always told when an alert fires (orchestrator responsibility).
    """
    if asked:
        return "asked"
    if sev == "critical" and emergency_alerts and (emergency_due or True):
        # Immediate critical + emergency consent → emergency alert.
        if sharing_level in ("auto_red", "full") or emergency_alerts:
            return "emergency" if emergency_alerts else ("auto_high" if sharing_level != "ask_only" else None)
    if sev == "critical":
        if emergency_alerts:
            return "emergency"
        if sharing_level in ("auto_red", "full"):
            return "auto_high"
        return None
    if sev == "high":
        if sharing_level in ("auto_red", "full"):
            return "auto_high"
        return None
    if sev == "medium":
        if sharing_level == "full":
            return "nudge"  # daily digest represented as a soft alert in the demo
        return None
    return None


def needs_probability_review(p: float | None, rule_floor: str) -> bool:
    """0.5–0.7 above the rule floor → human review."""
    if p is None:
        return False
    try:
        p = float(p)
    except (TypeError, ValueError):
        return False
    if 0.5 <= p < 0.7 and rule_floor == "low":
        return True
    return False
