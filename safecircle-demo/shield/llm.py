"""
Optional LLM layer (Anthropic Messages API, stdlib only — no SDK needed).

The LLM only CLASSIFIES: it returns signal ids and a category from fixed lists,
plus the text it read from a screenshot. It never writes the user-facing reply.
If ANTHROPIC_API_KEY is not set, the demo runs on rules alone.
"""
import json
import os
import re
import urllib.error
import urllib.request

from .replies import SIGNAL_TEXT, CATEGORY_NAMES

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are a scam-detection classifier protecting older adults in India.
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


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def model_name() -> str:
    return os.environ.get("SAFECIRCLE_MODEL", DEFAULT_MODEL)


def classify(text: str = "", image_b64: str = None, image_type: str = "image/jpeg", timeout: int = 45):
    """Return a validated dict, or None if the call fails for any reason."""
    if not available():
        return None
    content = []
    if image_b64:
        content.append({"type": "image", "source": {"type": "base64", "media_type": image_type, "data": image_b64}})
    content.append({"type": "text", "text": "Content to check:\n\n" + (text or "(see image)")})

    body = json.dumps({
        "model": model_name(),
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": content}],
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        detail = ""
        if isinstance(exc, urllib.error.HTTPError):
            try:
                detail = exc.read().decode("utf-8")[:300]
            except Exception:
                pass
        print(f"[llm] request failed: {exc} {detail}")
        return None

    raw = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        print("[llm] no JSON in response")
        return None
    try:
        out = json.loads(match.group(0))
    except json.JSONDecodeError:
        print("[llm] invalid JSON in response")
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
