"""Evaluate the trained stack on held-out test + samples.json."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ml import bert_model, data, gnn_model, xgb_model  # noqa: E402


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
    return float((ranks[y_sorted == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _f1_rec_fpr(y, p, thr=0.5):
    y = np.asarray(y)
    pred = (np.asarray(p) >= thr).astype(int)
    tp = ((pred == 1) & (y == 1)).sum()
    fp = ((pred == 1) & (y == 0)).sum()
    fn = ((pred == 0) & (y == 1)).sum()
    tn = ((pred == 0) & (y == 0)).sum()
    prec = tp / (tp + fp + 1e-9)
    rec = tp / (tp + fn + 1e-9)
    fpr = fp / (fp + tn + 1e-9)
    f1 = 2 * prec * rec / (prec + rec + 1e-9)
    return float(f1), float(rec), float(fpr)


def _ece(y, p, bins=10):
    y = np.asarray(y)
    p = np.asarray(p)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.sum() == 0:
            continue
        ece += (m.sum() / len(p)) * abs(y[m].mean() - p[m].mean())
    return float(ece)


def run_eval(models_dir: str, csv_path: str = None) -> dict:
    splits = data.load_splits(models_dir)
    if not splits:
        splits = data.prepare(csv_path or data.DEFAULT_CSV, models_dir)
    test = splits["test"]
    texts = test["text"].tolist()
    y = test["is_scam"].to_numpy()

    print(f"[eval] test n={len(texts)}")
    b_model, b_tok, b_dev = bert_model.load(os.path.join(models_dir, "bert"))
    g_model, g_vocab, g_dev = gnn_model.load(models_dir)
    xgb = xgb_model.load(models_dir)

    pb = bert_model.predict_proba(b_model, b_tok, texts, b_dev)
    pg = gnn_model.predict_proba(g_model, g_vocab, texts, g_dev)
    p = xgb_model.predict_proba(xgb, texts, pb, pg)

    f1, rec, fpr = _f1_rec_fpr(y, p)
    metrics = {
        "test_auroc": _auroc(y, p),
        "test_f1": f1,
        "scam_recall": rec,
        "genuine_fpr": fpr,
        "ece": _ece(y, p),
        "bert_auroc": _auroc(y, pb),
        "gnn_auroc": _auroc(y, pg),
        "n_test": int(len(y)),
    }

    # Per source if available
    if "source" in test.columns:
        by_src = {}
        for src, g in test.groupby("source"):
            idx = g.index.to_numpy()
            # test was reset; use positional via mask
            mask = test["source"].to_numpy() == src
            if mask.sum() < 5:
                continue
            f1s, recs, fprs = _f1_rec_fpr(y[mask], p[mask])
            by_src[str(src)] = {"auroc": _auroc(y[mask], p[mask]), "recall": recs, "fpr": fprs, "n": int(mask.sum())}
        metrics["by_source"] = by_src

    # samples.json smoke
    samples_path = os.path.join(ROOT, "samples.json")
    sample_rows = []
    if os.path.isfile(samples_path):
        samples = json.load(open(samples_path, encoding="utf-8"))
        st = [s["text"] for s in samples]
        spb = bert_model.predict_proba(b_model, b_tok, st, b_dev)
        spg = gnn_model.predict_proba(g_model, g_vocab, st, g_dev)
        sp = xgb_model.predict_proba(xgb, st, spb, spg)
        for s, prob in zip(samples, sp):
            sample_rows.append({
                "id": s["id"],
                "expected": s["expected"],
                "p_ml": float(prob),
                "flagged": bool(prob >= 0.5),
            })
        metrics["samples"] = sample_rows

    with open(os.path.join(models_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    lines = [
        "# SafeCircle ML report",
        "",
        f"- test AUROC: **{metrics['test_auroc']:.4f}**",
        f"- test F1: **{metrics['test_f1']:.4f}**",
        f"- scam recall: **{metrics['scam_recall']:.4f}** (target ≥ 0.95)",
        f"- genuine FPR: **{metrics['genuine_fpr']:.4f}** (target ≤ 0.05)",
        f"- ECE: {metrics['ece']:.4f}",
        f"- BERT AUROC: {metrics['bert_auroc']:.4f}",
        f"- GNN AUROC: {metrics['gnn_auroc']:.4f}",
        f"- n_test: {metrics['n_test']}",
        "",
    ]
    if sample_rows:
        lines.append("## samples.json")
        for r in sample_rows:
            lines.append(f"- `{r['id']}` expected={r['expected']} p={r['p_ml']:.3f} flagged={r['flagged']}")
    report = "\n".join(lines) + "\n"
    with open(os.path.join(models_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    return metrics


if __name__ == "__main__":
    models = os.path.join(ROOT, "models")
    run_eval(models)
