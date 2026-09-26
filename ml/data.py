"""Dataset loading, augmentation, and stratified splits."""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV = os.path.join(ROOT, "data", "master_scam_or_not.csv")
SEED = 42

SUSPECT_RE = re.compile(r"(?:^|\n)\s*Suspect:\s*", re.I)
INNOCENT_RE = re.compile(r"(?:^|\n)\s*Innocent:\s*", re.I)


def data_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _slice_dialogue(text: str, max_turns: int = 3) -> list[str]:
    """Slice Suspect/Innocent dialogues into first-k Suspect turns (forwarded-message length)."""
    if not text or "Suspect:" not in text:
        return [text] if text else []
    parts = SUSPECT_RE.split(text)
    # parts[0] is preamble; subsequent are suspect utterances (may include Innocent replies).
    suspect_turns = []
    for p in parts[1:]:
        # Keep only the suspect portion before next Innocent if present.
        chunk = INNOCENT_RE.split(p, maxsplit=1)[0].strip()
        if chunk:
            suspect_turns.append(chunk)
    if not suspect_turns:
        return [text[:2000]]
    out = []
    for k in range(1, min(len(suspect_turns), max_turns) + 1):
        out.append("\n".join(suspect_turns[:k])[:2000])
    return out


def load_dataframe(csv_path: str = DEFAULT_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["text"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() > 0]
    df["is_scam"] = df["is_scam"].astype(int)
    df["dataset_type"] = df["dataset_type"].fillna("unknown").astype(str)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    return df


def augment(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        text = r["text"]
        slices = _slice_dialogue(text) if "Suspect:" in text else [text[:2000]]
        for s in slices:
            rows.append({
                "text": s,
                "is_scam": int(r["is_scam"]),
                "dataset_type": r["dataset_type"],
                "source": r.get("source", ""),
                "scenario": r.get("scenario", ""),
            })
        # Also keep a truncated full text for long dialogues.
        if len(text) > 500 and "Suspect:" in text:
            rows.append({
                "text": text[:1500],
                "is_scam": int(r["is_scam"]),
                "dataset_type": r["dataset_type"],
                "source": r.get("source", ""),
                "scenario": r.get("scenario", ""),
            })
    out = pd.DataFrame(rows).drop_duplicates(subset=["text"]).reset_index(drop=True)
    return out


def make_splits(
    df: pd.DataFrame,
    seed: int = SEED,
    ratios=(0.70, 0.10, 0.10, 0.10),
) -> dict[str, pd.DataFrame]:
    """70 base-train / 10 stack / 10 val / 10 test, stratified by dataset_type × is_scam."""
    df = df.copy()
    df["_strata"] = df["dataset_type"].astype(str) + "_" + df["is_scam"].astype(str)
    # Collapse rare strata.
    vc = df["_strata"].value_counts()
    rare = set(vc[vc < 5].index)
    if rare:
        df.loc[df["_strata"].isin(rare), "_strata"] = "other_" + df["is_scam"].astype(str)

    train_ratio, stack_ratio, val_ratio, test_ratio = ratios
    rest_ratio = stack_ratio + val_ratio + test_ratio
    base, rest = train_test_split(
        df, test_size=rest_ratio, random_state=seed, stratify=df["_strata"]
    )
    # rest: stack / val / test proportional
    stack_frac = stack_ratio / rest_ratio
    val_frac = val_ratio / rest_ratio
    stack, rest2 = train_test_split(
        rest, test_size=1 - stack_frac, random_state=seed, stratify=rest["_strata"]
    )
    val_frac2 = val_frac / (val_frac + test_ratio)
    val, test = train_test_split(
        rest2, test_size=1 - val_frac2, random_state=seed, stratify=rest2["_strata"]
    )
    for part in (base, stack, val, test):
        part.drop(columns=["_strata"], inplace=True, errors="ignore")
    return {
        "base_train": base.reset_index(drop=True),
        "stack": stack.reset_index(drop=True),
        "val": val.reset_index(drop=True),
        "test": test.reset_index(drop=True),
    }


def save_splits(splits: dict, models_dir: str, csv_path: str):
    os.makedirs(models_dir, exist_ok=True)
    meta = {
        "seed": SEED,
        "data_hash": data_hash(csv_path),
        "counts": {k: len(v) for k, v in splits.items()},
        "pos_rate": {k: float(v["is_scam"].mean()) for k, v in splits.items()},
    }
    with open(os.path.join(models_dir, "split.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    for name, part in splits.items():
        part.to_csv(os.path.join(models_dir, f"split_{name}.csv"), index=False)
    return meta


def load_splits(models_dir: str) -> Optional[dict[str, pd.DataFrame]]:
    out = {}
    for name in ("base_train", "stack", "val", "test"):
        path = os.path.join(models_dir, f"split_{name}.csv")
        if not os.path.isfile(path):
            return None
        out[name] = pd.read_csv(path)
    return out


def prepare(csv_path: str = DEFAULT_CSV, models_dir: str = None, seed: int = SEED) -> dict:
    models_dir = models_dir or os.path.join(ROOT, "models")
    existing = load_splits(models_dir)
    if existing:
        print(f"[data] reusing splits in {models_dir}")
        return existing
    print(f"[data] loading {csv_path}")
    df = load_dataframe(csv_path)
    print(f"[data] {len(df)} rows after dedupe; augmenting…")
    aug = augment(df)
    print(f"[data] {len(aug)} rows after augment")
    splits = make_splits(aug, seed=seed)
    save_splits(splits, models_dir, csv_path)
    for k, v in splits.items():
        print(f"  {k}: {len(v)}  pos={v['is_scam'].mean():.3f}")
    return splits
