"""Inference bundle loader used by shield.ml_layer."""
from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np


class Bundle:
    def __init__(self, bert_model, bert_tok, bert_dev, gnn_model, gnn_vocab, gnn_dev, xgb, meta):
        self.bert_model = bert_model
        self.bert_tok = bert_tok
        self.bert_dev = bert_dev
        self.gnn_model = gnn_model
        self.gnn_vocab = gnn_vocab
        self.gnn_dev = gnn_dev
        self.xgb = xgb
        self.meta = meta

    def predict(self, text: str) -> dict:
        from ml import bert_model, gnn_model, xgb_model
        texts = [text or ""]
        pb = float(bert_model.predict_proba(self.bert_model, self.bert_tok, texts, self.bert_dev)[0])
        pg = float(gnn_model.predict_proba(self.gnn_model, self.gnn_vocab, texts, self.gnn_dev)[0])
        p = float(xgb_model.predict_proba(self.xgb, texts, [pb], [pg])[0])
        return {
            "p_bert": pb,
            "p_gnn": pg,
            "scam_probability": p,
        }


def load_bundle(models_dir: str) -> Optional[Bundle]:
    meta_path = os.path.join(models_dir, "meta.json")
    xgb_path = os.path.join(models_dir, "xgb.json")
    bert_dir = os.path.join(models_dir, "bert")
    if not (os.path.isfile(meta_path) and os.path.isfile(xgb_path)):
        return None
    # Prefer bert/best
    bert_path = os.path.join(bert_dir, "best") if os.path.isdir(os.path.join(bert_dir, "best")) else bert_dir
    if not os.path.isdir(bert_path):
        return None
    if not os.path.isfile(os.path.join(models_dir, "gnn.pt")):
        return None

    from ml import bert_model, gnn_model, xgb_model
    # Prefer CPU for server latency predictability unless CUDA is free; still allow CUDA.
    b_model, b_tok, b_dev = bert_model.load(bert_dir)
    g_model, g_vocab, g_dev = gnn_model.load(models_dir)
    xgb = xgb_model.load(models_dir)
    meta = json.load(open(meta_path, encoding="utf-8"))
    return Bundle(b_model, b_tok, b_dev, g_model, g_vocab, g_dev, xgb, meta)
