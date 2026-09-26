"""
Lazy ML inference singleton. Returns None when artifacts or deps are missing
so the server always degrades to rules (+ optional LLM).

Works with BERT-only checkpoints or the full BERT+GNN+XGBoost stack.
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
_state = {"loaded": False, "ok": False, "err": None, "bundle": None, "mode": None}


def available() -> bool:
    try:
        from ml.infer import bert_available
        return bert_available(MODELS_DIR)
    except Exception:
        best = os.path.join(MODELS_DIR, "bert", "best", "config.json")
        return os.path.isfile(best)


def status() -> dict:
    metrics = {}
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    if os.path.isfile(metrics_path):
        try:
            metrics = json.load(open(metrics_path, encoding="utf-8"))
        except Exception:
            metrics = {}

    meta = {}
    for path in (
        os.path.join(MODELS_DIR, "meta.json"),
        os.path.join(MODELS_DIR, "bert", "bert_meta.json"),
    ):
        if os.path.isfile(path):
            try:
                meta = json.load(open(path, encoding="utf-8"))
                break
            except Exception:
                pass

    mode = _state.get("mode")
    if not mode and available():
        try:
            from ml.infer import full_stack_available
            mode = "full" if full_stack_available(MODELS_DIR) else "bert_only"
        except Exception:
            mode = "bert_only"

    label = {
        "full": "BERT+GNN+XGB",
        "bert_only": "BERT",
    }.get(mode or "", None)

    return {
        "available": available(),
        "loaded": _state["ok"],
        "error": _state["err"],
        "mode": mode,
        "label": label,
        "backbone": meta.get("backbone", "xlm-roberta-base"),
        "val_f1": meta.get("best_val_f1") or metrics.get("test_f1"),
        "metrics": {
            "test_auroc": metrics.get("test_auroc"),
            "test_f1": metrics.get("test_f1") or meta.get("best_val_f1"),
            "scam_recall": metrics.get("scam_recall"),
            "genuine_fpr": metrics.get("genuine_fpr"),
            "best_val_f1": meta.get("best_val_f1"),
        },
    }


def warmup() -> bool:
    """Load weights eagerly (e.g. at server start) so the first check is fast."""
    if not available():
        return False
    _load()
    return bool(_state["ok"])


def _load():
    if _state["loaded"]:
        return
    with _lock:
        if _state["loaded"]:
            return
        _state["loaded"] = True
        try:
            from ml.infer import load_bundle
            bundle = load_bundle(MODELS_DIR)
            _state["bundle"] = bundle
            _state["ok"] = bundle is not None
            _state["mode"] = getattr(bundle, "mode", None) if bundle else None
            if not _state["ok"]:
                _state["err"] = "bundle missing"
            else:
                print(f"[ml_layer] loaded mode={_state['mode']} device={getattr(bundle, 'bert_dev', '?')}")
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
