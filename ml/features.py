"""Handcrafted features shared by training and inference."""
from __future__ import annotations

import os
import sys
from typing import Iterable

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shield import extract, rules  # noqa: E402

# Stable feature order.
SIGNAL_NAMES = sorted(rules.SIGNAL_PATTERNS.keys()) + sorted(rules.INTERNAL_SIGNALS) + [
    "known_reported", "suspicious_link", "fake_brand_link", "short_link", "apk_link",
]
# Deduplicate while preserving order.
_seen = set()
SIGNAL_NAMES = [s for s in SIGNAL_NAMES if not (s in _seen or _seen.add(s))]

FEATURE_NAMES = (
    [f"sig_{s}" for s in SIGNAL_NAMES]
    + ["n_phones", "n_upi", "n_links", "n_amounts", "has_amount"]
    + ["char_len", "digit_ratio", "url_ratio", "devanagari_ratio", "upper_ratio"]
    + ["rule_floor"]  # 0 low, 1 medium, 2 high
)


def _ratios(text: str) -> dict:
    text = text or ""
    n = max(len(text), 1)
    digits = sum(c.isdigit() for c in text) / n
    urls = len(extract.URL_RE.findall(text)) / n
    dev = sum(0x0900 <= ord(c) <= 0x097F for c in text) / n
    upper = sum(c.isupper() for c in text) / n
    return {
        "char_len": min(len(text), 5000) / 5000.0,
        "digit_ratio": digits,
        "url_ratio": min(urls * 50, 1.0),
        "devanagari_ratio": dev,
        "upper_ratio": upper,
    }


def vectorize(text: str) -> np.ndarray:
    entities = extract.extract(text)
    signals = rules.detect_signals(text) | extract.entity_signals(entities)
    floor, _ = rules.apply_playbooks(signals)
    floor_ord = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(floor, 0.0)
    ratios = _ratios(text)
    vals = []
    for s in SIGNAL_NAMES:
        vals.append(1.0 if s in signals else 0.0)
    vals += [
        float(len(entities["phones"])),
        float(len(entities["upi_ids"])),
        float(len(entities["links"])),
        float(len(entities["amounts"])),
        1.0 if entities["amounts"] else 0.0,
        ratios["char_len"],
        ratios["digit_ratio"],
        ratios["url_ratio"],
        ratios["devanagari_ratio"],
        ratios["upper_ratio"],
        floor_ord,
    ]
    return np.asarray(vals, dtype=np.float32)


def matrix(texts: Iterable[str]) -> np.ndarray:
    return np.vstack([vectorize(t) for t in texts])
