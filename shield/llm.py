"""
OpenAI adapter for SafeCircle agents.

All agents return JSON (or plain text for the demo takeover). The orchestrator
validates outputs in code; this module never raises into the request path.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

DEFAULT_MODEL = "gpt-4.1-mini"
API_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def model_name() -> str:
    return os.environ.get("SAFECIRCLE_MODEL", DEFAULT_MODEL)


def demo_takeover_enabled() -> bool:
    return os.environ.get("SAFECIRCLE_DEMO_TAKEOVER", "1").strip() not in ("0", "false", "False")


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=API_BASE, timeout=45.0)


def _parts_to_content(parts: list) -> list | str:
    """Convert mixed text/image parts into OpenAI content blocks."""
    if not parts:
        return ""
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts[0]
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append({"type": "text", "text": p})
        elif isinstance(p, dict) and p.get("type") == "image":
            media = p.get("media_type", "image/jpeg")
            data = p.get("data", "")
            out.append({
                "type": "image_url",
                "image_url": {"url": f"data:{media};base64,{data}"},
            })
        elif isinstance(p, dict) and p.get("type") == "text":
            out.append({"type": "text", "text": p.get("text", "")})
        else:
            out.append({"type": "text", "text": str(p)})
    return out


def _extract_json(raw: str) -> Optional[dict]:
    raw = re.sub(r"```(?:json)?|```", "", raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def chat_json(
    system: str,
    user_parts: list | str,
    *,
    timeout: int = 45,
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> Optional[dict]:
    """Call OpenAI with JSON mode. Returns a dict or None on any failure."""
    if not available():
        return None
    if isinstance(user_parts, str):
        user_parts = [user_parts]
    content = _parts_to_content(user_parts)
    last_err = None
    for attempt in range(2):
        try:
            client = _client()
            client = client.with_options(timeout=float(timeout))
            resp = client.chat.completions.create(
                model=model_name(),
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
            )
            raw = (resp.choices[0].message.content or "").strip()
            out = _extract_json(raw)
            if out is None:
                print("[llm] no JSON in response")
                return None
            return out
        except Exception as exc:
            last_err = exc
            print(f"[llm] chat_json attempt {attempt + 1} failed: {exc}")
            time.sleep(0.4 * (attempt + 1))
    print(f"[llm] chat_json gave up: {last_err}")
    return None


def chat_text(
    system: str,
    user_parts: list | str,
    *,
    timeout: int = 30,
    temperature: float = 0.3,
    max_tokens: int = 256,
) -> Optional[str]:
    """Call OpenAI for plain text (demo takeover). Returns stripped text or None."""
    if not available():
        return None
    if isinstance(user_parts, str):
        user_parts = [user_parts]
    content = _parts_to_content(user_parts)
    try:
        client = _client()
        client = client.with_options(timeout=float(timeout))
        resp = client.chat.completions.create(
            model=model_name(),
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        )
        return (resp.choices[0].message.content or "").strip() or None
    except Exception as exc:
        print(f"[llm] chat_text failed: {exc}")
        return None


# ---------- Backward-compatible classify() used by older analyse() paths ----------

from .replies import SIGNAL_TEXT, CATEGORY_NAMES  # noqa: E402

_CLASSIFY_SYSTEM = """You are a scam-detection classifier protecting older adults in India.
You receive a message, link, call description or screenshot that an older person found suspicious.
It may be in English, Hindi, Marathi, Hinglish or another Indian language.

Return ONLY a JSON object, with no prose and no markdown fences:
{
  "extracted_text": "all readable message text if an image was given, else empty string",
  "sender_shown": "sender name/number visible in a screenshot, else empty string",
  "signals": ["ids from the allowed signal list that are clearly present"],
  "category": "one id from the allowed category list",
  "risk": "low" | "medium" | "high",
  "confidence": number between 0 and 1,
  "note": "one short English sentence for a human reviewer"
}

Allowed signal ids: %s
Allowed category ids: %s

Guidance:
- Legitimate OTP SMS that say "do not share" are NOT otp_request.
- Normal family chat, delivery updates from official domains and bank alerts with no request are low.
- Treat requests for money, OTPs, PINs, app installs or screen sharing from unverified parties as high.
- Emotional manipulation followed by a money need (romance scams) is high even without keywords.
- When unsure, prefer "medium" with lower confidence rather than "low".
""" % (", ".join(sorted(SIGNAL_TEXT)), ", ".join(sorted(CATEGORY_NAMES)))


def classify(
    text: str = "",
    image_b64: str = None,
    image_type: str = "image/jpeg",
    timeout: int = 45,
) -> Optional[dict[str, Any]]:
    """Legacy classifier used by analyse(). Prefer agents.detection for new code."""
    parts: list = []
    if image_b64:
        parts.append({"type": "image", "media_type": image_type, "data": image_b64})
    parts.append("Content to check:\n\n" + (text or "(see image)"))
    out = chat_json(_CLASSIFY_SYSTEM, parts, timeout=timeout)
    if not out:
        return None
    risk = out.get("risk") if out.get("risk") in ("low", "medium", "high") else "medium"
    try:
        confidence = max(0.0, min(1.0, float(out.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "extracted_text": str(out.get("extracted_text") or "")[:4000],
        "sender_shown": str(out.get("sender_shown") or "")[:120],
        "signals": [s for s in out.get("signals", []) if s in SIGNAL_TEXT],
        "category": out.get("category") if out.get("category") in CATEGORY_NAMES else "generic",
        "risk": risk,
        "confidence": confidence,
        "note": str(out.get("note") or "")[:300],
    }
