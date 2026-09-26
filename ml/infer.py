"""Inference bundle loader used by shield.ml_layer.

Supports:
  - full stack: BERT + GNN + XGBoost (preferred when artifacts exist)
  - bert_only: fine-tuned XLM-RoBERTa alone (what we have after partial training)
"""
from __future__ import annotations

import json
import os
from typing import Optional


class Bundle:
    def __init__(
        self,
        bert_model,
        bert_tok,
        bert_dev,
        meta: dict,
        *,
        mode: str = "bert_only",
        gnn_model=None,
        gnn_vocab=None,
        gnn_dev=None,
        xgb=None,
    ):
        self.bert_model = bert_model
        self.bert_tok = bert_tok
        self.bert_dev = bert_dev
        self.gnn_model = gnn_model
        self.gnn_vocab = gnn_vocab
        self.gnn_dev = gnn_dev
        self.xgb = xgb
        self.meta = meta or {}
        self.mode = mode  # "full" | "bert_only"

    def predict(self, text: str) -> dict:
        from ml import bert_model

        texts = [text or ""]
        pb = float(
            bert_model.predict_proba(
                self.bert_model, self.bert_tok, texts, self.bert_dev
            )[0]
        )
        pg = None
        if self.mode == "full" and self.gnn_model is not None and self.xgb is not None:
            from ml import gnn_model, xgb_model

            pg = float(
                gnn_model.predict_proba(
                    self.gnn_model, self.gnn_vocab, texts, self.gnn_dev
                )[0]
            )
            p = float(xgb_model.predict_proba(self.xgb, texts, [pb], [pg])[0])
        else:
            # BERT-only: use classifier probability directly.
            p = pb
            pg = None
        return {
            "p_bert": pb,
            "p_gnn": pg,
            "scam_probability": p,
            "mode": self.mode,
        }


def _bert_dir(models_dir: str) -> Optional[str]:
    bert_dir = os.path.join(models_dir, "bert")
    best = os.path.join(bert_dir, "best")
    if os.path.isdir(best) and os.path.isfile(os.path.join(best, "config.json")):
        return bert_dir
    if os.path.isdir(bert_dir) and os.path.isfile(os.path.join(bert_dir, "config.json")):
        return bert_dir
    return None


def bert_available(models_dir: str) -> bool:
    return _bert_dir(models_dir) is not None


def full_stack_available(models_dir: str) -> bool:
    return (
        bert_available(models_dir)
        and os.path.isfile(os.path.join(models_dir, "xgb.json"))
        and os.path.isfile(os.path.join(models_dir, "gnn.pt"))
        and os.path.isfile(os.path.join(models_dir, "gnn_vocab.json"))
    )


def load_bundle(models_dir: str) -> Optional[Bundle]:
    bert_dir = _bert_dir(models_dir)
    if not bert_dir:
        return None

    from ml import bert_model

    device = os.environ.get("SAFECIRCLE_ML_DEVICE")  # e.g. "cpu" or "cuda"
    b_model, b_tok, b_dev = bert_model.load(bert_dir, device=device)

    meta_path = os.path.join(models_dir, "meta.json")
    bert_meta_path = os.path.join(models_dir, "bert", "bert_meta.json")
    meta = {}
    if os.path.isfile(meta_path):
        try:
            meta = json.load(open(meta_path, encoding="utf-8"))
        except Exception:
            meta = {}
    elif os.path.isfile(bert_meta_path):
        try:
            meta = json.load(open(bert_meta_path, encoding="utf-8"))
        except Exception:
            meta = {}
    meta.setdefault("backbone", getattr(bert_model, "BACKBONE", "xlm-roberta-base"))

    if full_stack_available(models_dir):
        from ml import gnn_model, xgb_model

        g_model, g_vocab, g_dev = gnn_model.load(models_dir, device=device)
        xgb = xgb_model.load(models_dir)
        meta["mode"] = "full"
        return Bundle(
            b_model,
            b_tok,
            b_dev,
            meta,
            mode="full",
            gnn_model=g_model,
            gnn_vocab=g_vocab,
            gnn_dev=g_dev,
            xgb=xgb,
        )

    meta["mode"] = "bert_only"
    return Bundle(b_model, b_tok, b_dev, meta, mode="bert_only")
