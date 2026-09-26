"""
Train SafeCircle ML stack: BERT → GNN → XGBoost.

    python -m ml.train --stage all
    python -m ml.train --stage bert
    python -m ml.train --stage gnn
    python -m ml.train --stage xgb
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ml import bert_model, data, gnn_model, xgb_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["bert", "gnn", "xgb", "all"], default="all")
    ap.add_argument("--csv", default=os.path.join(ROOT, "data", "master_scam_or_not.csv"))
    ap.add_argument("--models", default=os.path.join(ROOT, "models"))
    ap.add_argument("--epochs-bert", type=int, default=3)
    ap.add_argument("--epochs-gnn", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default=None)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-train", type=int, default=3000, help="cap BERT/GNN training rows (0=all)")
    args = ap.parse_args()

    os.makedirs(args.models, exist_ok=True)
    splits = data.prepare(args.csv, args.models, seed=args.seed)
    base, stack, val, test = splits["base_train"], splits["stack"], splits["val"], splits["test"]

    bert_dir = os.path.join(args.models, "bert")
    device = args.device

    if args.stage in ("bert", "all"):
        print("=== BERT ===", flush=True)
        bert_model.train(
            base["text"].tolist(),
            base["is_scam"].tolist(),
            val["text"].tolist(),
            val["is_scam"].tolist(),
            bert_dir,
            epochs=args.epochs_bert,
            batch_size=args.batch_size,
            device=device,
            max_train=args.max_train,
        )

    if args.stage in ("gnn", "all"):
        print("=== GNN ===", flush=True)
        gnn_model.train(
            base["text"].tolist(),
            base["is_scam"].tolist(),
            val["text"].tolist(),
            val["is_scam"].tolist(),
            args.models,
            epochs=args.epochs_gnn,
            device=device,
            max_train=args.max_train or 4000,
        )

    if args.stage in ("xgb", "all"):
        print("=== XGB stacker ===")
        import torch
        # Load BERT + GNN and score stack/val.
        b_model, b_tok, b_dev = bert_model.load(bert_dir, device=device)
        g_model, g_vocab, g_dev = gnn_model.load(args.models, device=device)

        def score(texts):
            pb = bert_model.predict_proba(b_model, b_tok, texts, b_dev)
            pg = gnn_model.predict_proba(g_model, g_vocab, texts, g_dev)
            return pb, pg

        print("[xgb] scoring stack split…")
        pb_s, pg_s = score(stack["text"].tolist())
        print("[xgb] scoring val split…")
        pb_v, pg_v = score(val["text"].tolist())
        # Cache for evaluate
        np_save = {
            "stack_p_bert": pb_s.tolist(),
            "stack_p_gnn": pg_s.tolist(),
            "val_p_bert": pb_v.tolist(),
            "val_p_gnn": pg_v.tolist(),
        }
        with open(os.path.join(args.models, "oof_probs.json"), "w") as f:
            json.dump(np_save, f)

        xgb_model.train(
            stack["text"].tolist(),
            stack["is_scam"].tolist(),
            val["text"].tolist(),
            val["is_scam"].tolist(),
            pb_s, pg_s, pb_v, pg_v,
            args.models,
        )

        meta = {
            "backbone": bert_model.BACKBONE,
            "feature_order": xgb_model.FEATURE_ORDER,
            "data_hash": data.data_hash(args.csv),
            "policy_version": "2.0",
            "threshold": 0.5,
        }
        with open(os.path.join(args.models, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        print(f"[train] wrote meta.json → {args.models}")

    # Always try evaluate at end of all
    if args.stage == "all":
        from ml.evaluate import run_eval
        run_eval(args.models, args.csv)


if __name__ == "__main__":
    main()
