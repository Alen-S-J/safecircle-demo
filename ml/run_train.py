"""
Robust staged trainer for Windows/GPU with limited VRAM.
Runs BERT → GNN → XGB → eval, clearing CUDA between stages.
"""
from __future__ import annotations

import gc
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

MODELS = os.path.join(ROOT, "models")
os.makedirs(MODELS, exist_ok=True)


def _free():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def main():
    from ml import data, bert_model, gnn_model, xgb_model

    print("[1/4] prepare splits", flush=True)
    splits = data.prepare(os.path.join(ROOT, "data", "master_scam_or_not.csv"), MODELS)
    base, stack, val = splits["base_train"], splits["stack"], splits["val"]

    print("[2/4] BERT", flush=True)
    bert_dir = os.path.join(MODELS, "bert")
    bert_model.train(
        base["text"].tolist(),
        base["is_scam"].tolist(),
        val["text"].tolist(),
        val["is_scam"].tolist(),
        bert_dir,
        epochs=2,
        batch_size=8,
        max_train=2500,
        device="cuda",
    )
    _free()

    print("[3/4] GNN", flush=True)
    gnn_model.train(
        base["text"].tolist(),
        base["is_scam"].tolist(),
        val["text"].tolist(),
        val["is_scam"].tolist(),
        MODELS,
        epochs=3,
        max_train=2500,
        device="cuda",
    )
    _free()

    print("[4/4] XGB stacker", flush=True)
    b_model, b_tok, b_dev = bert_model.load(bert_dir, device="cuda")
    g_model, g_vocab, g_dev = gnn_model.load(MODELS, device="cuda")

    def score(texts):
        pb = bert_model.predict_proba(b_model, b_tok, texts, b_dev, batch_size=16)
        pg = gnn_model.predict_proba(g_model, g_vocab, texts, g_dev)
        return pb, pg

    print("  scoring stack…", flush=True)
    pb_s, pg_s = score(stack["text"].tolist())
    print("  scoring val…", flush=True)
    pb_v, pg_v = score(val["text"].tolist())
    with open(os.path.join(MODELS, "oof_probs.json"), "w") as f:
        json.dump({
            "stack_p_bert": pb_s.tolist(),
            "stack_p_gnn": pg_s.tolist(),
            "val_p_bert": pb_v.tolist(),
            "val_p_gnn": pg_v.tolist(),
        }, f)
    xgb_model.train(
        stack["text"].tolist(), stack["is_scam"].tolist(),
        val["text"].tolist(), val["is_scam"].tolist(),
        pb_s, pg_s, pb_v, pg_v, MODELS,
    )
    meta = {
        "backbone": bert_model.BACKBONE,
        "feature_order": xgb_model.FEATURE_ORDER,
        "data_hash": data.data_hash(os.path.join(ROOT, "data", "master_scam_or_not.csv")),
        "policy_version": "2.0",
        "threshold": 0.5,
        "max_train": 2500,
        "epochs_bert": 2,
        "epochs_gnn": 3,
    }
    with open(os.path.join(MODELS, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    del b_model, g_model
    _free()

    print("[eval]", flush=True)
    from ml.evaluate import run_eval
    run_eval(MODELS)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
