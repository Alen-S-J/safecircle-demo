"""Fine-tune XLM-RoBERTa for scam classification."""
from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

BACKBONE = "xlm-roberta-base"
MAX_LEN = 256


class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer):
        self.texts = list(texts)
        self.labels = list(labels)
        self.tok = tokenizer

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, i):
        enc = self.tok(
            self.texts[i],
            truncation=True,
            max_length=MAX_LEN,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(int(self.labels[i]), dtype=torch.long),
        }


def _f1(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    tp = ((y_pred == 1) & (y_true == 1)).sum()
    fp = ((y_pred == 1) & (y_true == 0)).sum()
    fn = ((y_pred == 0) & (y_true == 1)).sum()
    prec = tp / (tp + fp + 1e-9)
    rec = tp / (tp + fn + 1e-9)
    return 2 * prec * rec / (prec + rec + 1e-9)


@torch.no_grad()
def predict_proba(model, tokenizer, texts, device, batch_size=32) -> np.ndarray:
    model.eval()
    probs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(batch, truncation=True, max_length=MAX_LEN, padding=True, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        logits = model(**enc).logits
        p = torch.softmax(logits, dim=-1)[:, 1].detach().cpu().numpy()
        probs.append(p)
    return np.concatenate(probs) if probs else np.array([])


def train(
    train_texts,
    train_labels,
    val_texts,
    val_labels,
    out_dir: str,
    *,
    epochs: int = 3,
    batch_size: int = 8,
    lr: float = 2e-5,
    device: str = None,
    backbone: str = BACKBONE,
    max_train: int = 0,
) -> dict:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(out_dir, exist_ok=True)
    if max_train and len(train_texts) > max_train:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(train_texts), max_train, replace=False)
        train_texts = [train_texts[i] for i in idx]
        train_labels = [train_labels[i] for i in idx]
    print(f"[bert] device={device} backbone={backbone} n_train={len(train_texts)} batch={batch_size}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(backbone)
    model = AutoModelForSequenceClassification.from_pretrained(backbone, num_labels=2)
    model.to(device)

    train_ds = TextDataset(train_texts, train_labels, tokenizer)
    val_ds = TextDataset(val_texts, val_labels, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = max(1, len(train_loader) * epochs)
    sched = get_linear_schedule_with_warmup(optim, int(0.06 * total_steps), total_steps)
    use_amp = device.startswith("cuda")
    # torch.cuda.amp is more compatible across versions than torch.amp on some Windows builds
    try:
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
        autocast_ctx = lambda: torch.cuda.amp.autocast(enabled=use_amp)
    except Exception:
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
        autocast_ctx = lambda: torch.amp.autocast("cuda", enabled=use_amp)

    best_f1, best_path = -1.0, os.path.join(out_dir, "best")
    history = []

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for step_i, batch in enumerate(train_loader):
            optim.zero_grad(set_to_none=True)
            batch = {k: v.to(device) for k, v in batch.items()}
            with autocast_ctx():
                out = model(**batch)
                loss = out.loss
            if use_amp:
                scaler.scale(loss).backward()
                scaler.step(optim)
                scaler.update()
            else:
                loss.backward()
                optim.step()
            sched.step()
            total_loss += float(loss.item())
            if step_i and step_i % 50 == 0:
                print(f"[bert] epoch {epoch + 1} step {step_i}/{len(train_loader)} loss={total_loss / (step_i + 1):.4f}", flush=True)
        # Val
        model.eval()
        ys, ps = [], []
        with torch.no_grad():
            for batch in val_loader:
                labels = batch.pop("labels")
                batch = {k: v.to(device) for k, v in batch.items()}
                logits = model(**batch).logits
                prob = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
                ys.extend(labels.numpy().tolist())
                ps.extend(prob.tolist())
        pred = (np.array(ps) >= 0.5).astype(int)
        f1 = float(_f1(ys, pred))
        avg_loss = total_loss / max(1, len(train_loader))
        history.append({"epoch": epoch + 1, "loss": avg_loss, "val_f1": f1})
        print(f"[bert] epoch {epoch + 1}/{epochs} loss={avg_loss:.4f} val_f1={f1:.4f}")
        if f1 > best_f1:
            best_f1 = f1
            model.save_pretrained(best_path)
            tokenizer.save_pretrained(best_path)
            with open(os.path.join(out_dir, "bert_meta.json"), "w") as f:
                json.dump({"best_val_f1": best_f1, "backbone": backbone, "history": history}, f, indent=2)

    return {"best_val_f1": best_f1, "history": history, "path": best_path}


def load(out_dir: str, device: str = None):
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    path = os.path.join(out_dir, "best") if os.path.isdir(os.path.join(out_dir, "best")) else out_dir
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path)
    model.to(device)
    model.eval()
    return model, tokenizer, device
