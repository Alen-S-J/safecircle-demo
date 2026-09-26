"""
Pure-PyTorch GCN over a per-message token+signal graph.
No torch_geometric dependency.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from . import features as feat_mod

TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+|[^\w\s]", re.UNICODE)
VOCAB_SIZE = 20000
HASH_BUCKETS = 1024
WINDOW = 2
MAX_NODES = 180
EMBED_DIM = 64
HIDDEN = 64


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.strip()][:400]


def build_vocab(texts, max_size=VOCAB_SIZE) -> dict:
    cnt = Counter()
    for t in texts:
        cnt.update(tokenize(t))
    vocab = {"<pad>": 0, "<unk>": 1, "<hash>": 2}
    for w, _ in cnt.most_common(max_size - len(vocab) - 64):
        if w not in vocab:
            vocab[w] = len(vocab)
    # Reserve signal hub ids.
    for s in feat_mod.SIGNAL_NAMES:
        key = f"SIG::{s}"
        if key not in vocab:
            vocab[key] = len(vocab)
    for e in ("ENT::phone", "ENT::upi", "ENT::link", "ENT::amount"):
        if e not in vocab:
            vocab[e] = len(vocab)
    return vocab


def _hash_id(token: str, vocab: dict) -> int:
    # Stable hash into reserved bucket range near end — use unk + hash mix via vocab <hash>.
    return vocab["<unk>"] if token not in vocab else vocab[token]


def build_graph(text: str, vocab: dict, signals: set | None = None, entities: dict | None = None):
    """Return node_ids [N], edge_index [2,E] (undirected), for one message."""
    tokens = tokenize(text)
    node_ids = []
    for t in tokens[: MAX_NODES - 40]:
        if t in vocab:
            node_ids.append(vocab[t])
        else:
            # Hash bucket via simple modular offset from <hash>.
            h = (hash(t) % HASH_BUCKETS) + 3
            # Clamp into vocab range using unk if needed.
            node_ids.append(h if h < len(vocab) else vocab["<unk>"])

    # Signal / entity hubs.
    signals = signals or set()
    entities = entities or {}
    hub_indices = []
    for s in signals:
        key = f"SIG::{s}"
        if key in vocab and len(node_ids) < MAX_NODES:
            hub_indices.append(len(node_ids))
            node_ids.append(vocab[key])
    for kind, present in (
        ("ENT::phone", bool(entities.get("phones"))),
        ("ENT::upi", bool(entities.get("upi_ids"))),
        ("ENT::link", bool(entities.get("links"))),
        ("ENT::amount", bool(entities.get("amounts"))),
    ):
        if present and kind in vocab and len(node_ids) < MAX_NODES:
            hub_indices.append(len(node_ids))
            node_ids.append(vocab[kind])

    n = len(node_ids)
    if n == 0:
        node_ids = [vocab["<unk>"]]
        n = 1

    edges = set()
    n_tok = n - len(hub_indices)
    for i in range(n_tok):
        for j in range(i + 1, min(i + 1 + WINDOW, n_tok)):
            edges.add((i, j))
            edges.add((j, i))
    # Connect hubs to all token nodes (star).
    for h in hub_indices:
        for i in range(n_tok):
            edges.add((h, i))
            edges.add((i, h))
    # Self loops.
    for i in range(n):
        edges.add((i, i))

    if not edges:
        edges.add((0, 0))
    ei = torch.tensor(list(edges), dtype=torch.long).t().contiguous()  # [2, E]
    x = torch.tensor(node_ids, dtype=torch.long)
    return x, ei


def normalize_adj(edge_index: torch.Tensor, num_nodes: int) -> torch.Tensor:
    """Return sparse-friendly dense normalized A for small graphs."""
    A = torch.zeros(num_nodes, num_nodes, dtype=torch.float32)
    src, dst = edge_index
    A[src, dst] = 1.0
    deg = A.sum(dim=1).clamp(min=1.0)
    d_inv_sqrt = deg.pow(-0.5)
    return d_inv_sqrt.unsqueeze(1) * A * d_inv_sqrt.unsqueeze(0)


class GCNLayer(nn.Module):
    def __init__(self, in_dim, out_dim):
        super().__init__()
        self.lin = nn.Linear(in_dim, out_dim)

    def forward(self, H, A_hat):
        return self.lin(A_hat @ H)


class ScamGNN(nn.Module):
    def __init__(self, vocab_size, embed_dim=EMBED_DIM, hidden=HIDDEN):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.gcn1 = GCNLayer(embed_dim, hidden)
        self.gcn2 = GCNLayer(hidden, hidden)
        self.mlp = nn.Sequential(
            nn.Linear(hidden * 2, hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden, 1),
        )

    def forward(self, node_ids, A_hat):
        H = self.emb(node_ids)
        H = F.relu(self.gcn1(H, A_hat))
        H = self.gcn2(H, A_hat)
        mean_p = H.mean(dim=0)
        max_p = H.max(dim=0).values
        return self.mlp(torch.cat([mean_p, max_p], dim=-1)).squeeze(-1)


class GraphDataset(Dataset):
    def __init__(self, texts, labels, vocab):
        import sys
        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from shield import extract, rules
        self.items = []
        for t, y in zip(texts, labels):
            ents = extract.extract(t)
            sigs = rules.detect_signals(t) | extract.entity_signals(ents)
            x, ei = build_graph(t, vocab, sigs, ents)
            A = normalize_adj(ei, x.size(0))
            self.items.append((x, A, float(y)))

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        x, A, y = self.items[i]
        return x, A, torch.tensor(y, dtype=torch.float32)


def collate_skip(batch):
    # Variable-size graphs — train one-by-one in a micro-batch loop; DataLoader batch_size=1.
    return batch[0]


@torch.no_grad()
def predict_proba(model, vocab, texts, device, batch_hint=1) -> np.ndarray:
    import sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from shield import extract, rules
    model.eval()
    probs = []
    for t in texts:
        ents = extract.extract(t)
        sigs = rules.detect_signals(t) | extract.entity_signals(ents)
        x, ei = build_graph(t, vocab, sigs, ents)
        A = normalize_adj(ei, x.size(0)).to(device)
        x = x.to(device)
        logit = model(x, A)
        probs.append(float(torch.sigmoid(logit).item()))
    return np.asarray(probs, dtype=np.float32)


def _auroc(y, p):
    y = np.asarray(y)
    p = np.asarray(p)
    if len(np.unique(y)) < 2:
        return 0.5
    order = np.argsort(p)
    y_sorted = y[order]
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = np.arange(1, len(y) + 1)
    # Mann-Whitney
    sum_ranks_pos = ranks[y_sorted == 1].sum()
    return float((sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def train(
    train_texts,
    train_labels,
    val_texts,
    val_labels,
    out_dir: str,
    *,
    epochs: int = 4,
    lr: float = 1e-3,
    device: str = None,
    max_train: int = 4000,
) -> dict:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(out_dir, exist_ok=True)

    # Subsample for graph build speed if huge.
    if len(train_texts) > max_train:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(train_texts), max_train, replace=False)
        train_texts = [train_texts[i] for i in idx]
        train_labels = [train_labels[i] for i in idx]

    print(f"[gnn] building vocab on {len(train_texts)} texts…")
    vocab = build_vocab(train_texts)
    with open(os.path.join(out_dir, "gnn_vocab.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f)

    print(f"[gnn] building graphs…")
    train_ds = GraphDataset(train_texts, train_labels, vocab)
    # Cap val for speed
    val_cap = min(800, len(val_texts))
    val_ds = GraphDataset(val_texts[:val_cap], val_labels[:val_cap], vocab)

    model = ScamGNN(len(vocab)).to(device)
    optim = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    pos = sum(train_labels)
    neg = len(train_labels) - pos
    pos_weight = torch.tensor([neg / max(pos, 1)], device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_auroc, best_state = -1.0, None
    history = []
    for epoch in range(epochs):
        model.train()
        total = 0.0
        order = np.random.permutation(len(train_ds))
        for i in order:
            x, A, y = train_ds[int(i)]
            x, A, y = x.to(device), A.to(device), y.to(device)
            optim.zero_grad(set_to_none=True)
            logit = model(x, A)
            loss = loss_fn(logit, y)
            loss.backward()
            optim.step()
            total += float(loss.item())
        # Val
        model.eval()
        ys, ps = [], []
        with torch.no_grad():
            for i in range(len(val_ds)):
                x, A, y = val_ds[i]
                logit = model(x.to(device), A.to(device))
                ps.append(float(torch.sigmoid(logit).item()))
                ys.append(float(y.item()))
        au = _auroc(ys, ps)
        avg = total / max(1, len(train_ds))
        history.append({"epoch": epoch + 1, "loss": avg, "val_auroc": au})
        print(f"[gnn] epoch {epoch + 1}/{epochs} loss={avg:.4f} val_auroc={au:.4f}")
        if au > best_auroc:
            best_auroc = au
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state:
        model.load_state_dict(best_state)
    torch.save({"state_dict": model.state_dict(), "vocab_size": len(vocab)}, os.path.join(out_dir, "gnn.pt"))
    with open(os.path.join(out_dir, "gnn_meta.json"), "w") as f:
        json.dump({"best_val_auroc": best_auroc, "history": history, "vocab_size": len(vocab)}, f, indent=2)
    return {"best_val_auroc": best_auroc, "history": history, "path": out_dir}


def load(out_dir: str, device: str = None):
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    with open(os.path.join(out_dir, "gnn_vocab.json"), encoding="utf-8") as f:
        vocab = json.load(f)
    ckpt = torch.load(os.path.join(out_dir, "gnn.pt"), map_location=device, weights_only=True)
    model = ScamGNN(ckpt.get("vocab_size") or len(vocab))
    model.load_state_dict(ckpt["state_dict"])
    model.to(device)
    model.eval()
    return model, vocab, device
