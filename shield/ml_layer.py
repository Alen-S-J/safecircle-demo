"""
Lazy ML inference singleton. Returns None when artifacts or deps are missing
so the server always degrades to rules (+ optional LLM).
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.environ.get("SAFECIRCLE_MODELS", os.path.join(ROOT, "models"))

_lock = threading.Lock()
_state = {"loaded": False, "ok": False, "err": None, "bundle": None}


def available() -> bool:
    meta = os.path.join(MODELS_DIR, "meta.json")
    return os.path.isfile(meta) and (
        os.path.isdir(os.path.join(MODELS_DIR, "bert"))
        or os.path.isfile(os.path.join(MODELS_DIR, "xgb.json"))
    )


def status() -> dict:
    metrics = {}
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    if os.path.isfile(metrics_path):
        try:
            metrics = json.load(open(metrics_path, encoding="utf-8"))
        except Exception:
            metrics = {}
    meta = {}
    meta_path = os.path.join(MODELS_DIR, "meta.json")
    if os.path.isfile(meta_path):
        try:
            meta = json.load(open(meta_path, encoding="utf-8"))
        except Exception:
            meta = {}
    return {
        "available": available(),
        "loaded": _state["ok"],
        "error": _state["err"],
        "backbone": meta.get("backbone", "xlm-roberta-base"),
        "metrics": {
            "test_auroc": metrics.get("test_auroc"),
            "test_f1": metrics.get("test_f1"),
            "scam_recall": metrics.get("scam_recall"),
            "genuine_fpr": metrics.get("genuine_fpr"),
        } if metrics else {},
    }


def _load():
    if _state["loaded"]:
        return
    with _lock:
        if _state["loaded"]:
            return
        _state["loaded"] = True
        try:
            from ml.infer import load_bundle
            _state["bundle"] = load_bundle(MODELS_DIR)
            _state["ok"] = _state["bundle"] is not None
            if not _state["ok"]:
                _state["err"] = "bundle missing"
        except Exception as exc:
            _state["err"] = str(exc)
            _state["ok"] = False
            print(f"[ml_layer] load failed: {exc}")


def predict(text: str) -> Optional[dict]:
    if not text or not available():
        return None
    _load()
    if not _state["ok"] or _state["bundle"] is None:
        return None
    t0 = time.time()
    try:
        out = _state["bundle"].predict(text)
        out["latency_ms"] = int((time.time() - t0) * 1000)
        return out
    except Exception as exc:
        print(f"[ml_layer] predict error: {exc}")
        return None
