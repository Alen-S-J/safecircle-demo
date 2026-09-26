"""XGBoost stacker on [p_bert, p_gnn, handcrafted features]."""
from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
import xgboost as xgb

from . import features as feat_mod


def _auroc(y, p):
    y = np.asarray(y).astype(float)
    p = np.asarray(p).astype(float)
    if len(np.unique(y)) < 2:
        return 0.5
    order = np.argsort(p)
    y_sorted = y[order]
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = np.arange(1, len(y) + 1)
    sum_ranks_pos = ranks[y_sorted == 1].sum()
    return float((sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _f1(y, p, thr=0.5):
    y = np.asarray(y)
    pred = (np.asarray(p) >= thr).astype(int)
    tp = ((pred == 1) & (y == 1)).sum()
    fp = ((pred == 1) & (y == 0)).sum()
    fn = ((pred == 0) & (y == 1)).sum()
    prec = tp / (tp + fp + 1e-9)
    rec = tp / (tp + fn + 1e-9)
    return float(2 * prec * rec / (prec + rec + 1e-9))


def build_matrix(texts, p_bert, p_gnn) -> np.ndarray:
    Xf = feat_mod.matrix(texts)
    pb = np.asarray(p_bert, dtype=np.float32).reshape(-1, 1)
    pg = np.asarray(p_gnn, dtype=np.float32).reshape(-1, 1)
    return np.hstack([pb, pg, Xf])


FEATURE_ORDER = ["p_bert", "p_gnn"] + list(feat_mod.FEATURE_NAMES)


def train(
    stack_texts,
    stack_labels,
    val_texts,
    val_labels,
    p_bert_stack,
    p_gnn_stack,
    p_bert_val,
    p_gnn_val,
    out_dir: str,
) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    X_stack = build_matrix(stack_texts, p_bert_stack, p_gnn_stack)
    X_val = build_matrix(val_texts, p_bert_val, p_gnn_val)
    y_stack = np.asarray(stack_labels)
    y_val = np.asarray(val_labels)

    pos = max(1, int(y_stack.sum()))
    neg = max(1, int(len(y_stack) - pos))
    spw = neg / pos

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="auc",
        scale_pos_weight=spw,
        early_stopping_rounds=30,
        n_jobs=4,
    )
    model.fit(X_stack, y_stack, eval_set=[(X_val, y_val)], verbose=False)
    p_val = model.predict_proba(X_val)[:, 1]
    metrics = {
        "val_auroc": _auroc(y_val, p_val),
        "val_f1": _f1(y_val, p_val),
        "best_iteration": int(getattr(model, "best_iteration", 0) or 0),
        "scale_pos_weight": spw,
    }
    print(f"[xgb] val_auroc={metrics['val_auroc']:.4f} val_f1={metrics['val_f1']:.4f}")
    model.save_model(os.path.join(out_dir, "xgb.json"))
    with open(os.path.join(out_dir, "xgb_meta.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


def load(out_dir: str):
    model = xgb.XGBClassifier()
    model.load_model(os.path.join(out_dir, "xgb.json"))
    return model


def predict_proba(model, texts, p_bert, p_gnn) -> np.ndarray:
    X = build_matrix(texts, p_bert, p_gnn)
    return model.predict_proba(X)[:, 1]
