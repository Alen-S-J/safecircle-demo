"""Content wrapping and case summaries for agent prompts."""
from __future__ import annotations

from typing import Any


def untrusted(text: str, source: str = "forwarded_message", message_id: str = "") -> str:
    mid = f' id="{message_id}"' if message_id else ""
    return (
        f'<untrusted_content source="{source}"{mid}>\n'
        f"{text or ''}\n"
        f"</untrusted_content>"
    )


def case_summary(case: dict, facts: list | None = None) -> str:
    facts = facts or []
    fact_bits = ", ".join(
        f"{f['fact']}" + (f" ({f.get('quote', '')[:40]})" if f.get("quote") else "")
        for f in facts
        if f.get("value")
    ) or "none"
    signals = case.get("signals") or []
    if isinstance(signals, str):
        signals = []
    return (
        f"<case_summary>\n"
        f"stage: {case.get('stage', 'contact')}\n"
        f"severity: {case.get('severity', 'none')}\n"
        f"category: {case.get('category', 'none')}\n"
        f"risk: {case.get('risk', 'low')}\n"
        f"language: {case.get('lang', 'en')}\n"
        f"signals: {', '.join(signals[:12]) or 'none'}\n"
        f"facts: {fact_bits}\n"
        f"scam_probability: {case.get('scam_probability', 0)}\n"
        f"</case_summary>"
    )


def rules_result_block(signals: set, floor: str, category: str, stage: str, entities: dict) -> str:
    return (
        f"<rules_result>\n"
        f"signals: {sorted(signals)}\n"
        f"floor: {floor}\n"
        f"category: {category}\n"
        f"stage: {stage}\n"
        f"entities: {entities}\n"
        f"</rules_result>"
    )


def timeline_block(items: list[dict]) -> str:
    parts = ["<timeline>"]
    for it in items:
        parts.append(untrusted(it.get("text", ""), source=it.get("role", "other"), message_id=it.get("message_id", "")))
    parts.append("</timeline>")
    return "\n".join(parts)
