# SafeCircle: local demo

A scam-check companion for older adults in India, with a family view. The elder
forwards anything suspicious and gets a plain-language verdict in English, Hindi
or Marathi. Detection uses **deterministic rules**, an optional **ML stack**
(BERT + GNN + XGBoost), and optional **OpenAI agents** (Detection, Reply
Assistant, Judge). **Code decides; models advise.**

## Run it

Python 3.9+. Core server needs only the stdlib + `openai` (for AI mode).

```bash
pip install -r requirements.txt          # openai client
# optional ML inference/training:
pip install -r requirements-ml.txt

copy .env.example .env                   # add OPENAI_API_KEY=
python server.py
```

- Elder + family UI: http://localhost:8000  
- Three-panel demo: http://localhost:8000/demo.html  

```bash
python server.py --host 0.0.0.0   # phone on same Wi-Fi
python server.py --no-ai          # rules (+ ML) only
```

### Environment

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Enables Detection / Reply Assistant / Judge / demo takeover |
| `SAFECIRCLE_MODEL` | Default `gpt-4.1-mini` |
| `SAFECIRCLE_DEMO_TAKEOVER` | `1` (default) allows guarded demo takeover; `0` disables |
| `SAFECIRCLE_DB` | SQLite path (default `data/safecircle.db`) |
| `SAFECIRCLE_MODELS` | ML artifacts dir (default `models/`) |

## Three-panel demo (`/demo.html`)

1. **Threat channel (left)** — type as Scammer or User. Scammer bubbles get
   “Forward to SafeCircle”; User bubbles get “Tell SafeCircle” (elder role →
   compliance/loss detection). After demo takeover, agent replies appear here
   as teal “SafeCircle Agent” bubbles.
2. **SafeCircle (middle)** — verdict card (severity / stage / ML probability),
   agent log (rules → ML → detection → judge), “Suggest a reply” (Reply
   Assistant: Don’t reply first), and optional “Agent takes over (demo)”.
3. **Family (right)** — Rohan’s view, polled every 2.5s. Emergency / asked /
   nudge cards; emergency-alerts toggle.

## How detection works (policy v2)

```
item → rules (signals, floor, stage)
     → ML (p_bert, p_gnn → XGBoost → scam_probability)
     → Agent 1 Detection (JSON, schema-validated)
     → append-only facts
     → severity(stage, imminence, signals, floor)   # never drops automatically
     → Judge on event triggers
     → templates to elder (+ 1930 recovery on loss)
     → family alerts per sharing level + emergency consent
     → audit log
```

Severity axes: **category** (multi-label), **stage** (contact→hook→ask→compliance→loss),
**imminence** (days/hours/minutes). Models never set severity directly.

Golden rules enforced in code: no tools that pay/click/send; invalid JSON discarded;
severity = max(rule floor, computed); facts append-only; elder always told when
family is alerted; injection text → `ai_manipulation_attempt` (≥ high).

## ML layer

```bash
python -u ml/run_train.py          # BERT → GNN → XGBoost → metrics
# or:
python -m ml.train --stage all --max-train 3000 --batch-size 8
python -m ml.evaluate
```

Artifacts land in `models/` (gitignored): `bert/`, `gnn.pt`, `gnn_vocab.json`,
`xgb.json`, `meta.json`, `metrics.json`, `report.md`. If artifacts are missing,
the server degrades to rules (+ AI if keyed).

## Agents

| Agent | Role |
|---|---|
| Detection | Classify one item → det-2.0 JSON |
| Reply Assistant | 1–3 drafts; elder sends; draft validator in code |
| Judge | Event-driven case audit; can raise severity only |
| Demo takeover | Optional; same draft validator; clearly labelled |

## API (additions)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/check` | `{text?, image?, lang, case_id?, role?}` → verdict + trace |
| GET | `/api/cases/{id}` | Timeline, facts, audit |
| POST | `/api/agent/draft` | Reply Assistant (reply-2.0) |
| POST | `/api/agent/engage` | Demo takeover (gated) |
| POST | `/api/cases/{id}/judge` | Force Judge |
| POST | `/api/cases/{id}/override` | Human override (logged; facts kept) |
| GET | `/api/status` | `{ai, provider, model, ml, policy_version, demo_takeover}` |

Existing endpoints (`ask-family`, `report`, `advice`, `guardian`, `settings`,
`alerts/.../handled`, `reset`) are unchanged.

## Tests & eval

```bash
python -m unittest tests.test_v2 -v
python eval.py              # rules only on samples.json
python eval.py --ml         # include ML probabilities
python eval.py --ai         # rules + OpenAI
```

## Architecture map

| Path | What it is |
|---|---|
| `server.py` | HTTP API |
| `shield/orchestrator.py` | Policy main loop |
| `shield/policy.py` | Severity / imminence / escalation |
| `shield/agents/` | Detection, Reply Assistant, Judge, takeover |
| `shield/ml_layer.py` | Lazy ML inference |
| `ml/` | Train / eval / infer |
| `static/demo.html` | Three-panel demo |
| `static/index.html` | Elder + family UI |

## Known limits

- Sample chips were written alongside the rules — they are not a real accuracy proof.
- Train on the provided CSV for a demo-grade stack; pilot needs a consented real test set.
- Demo takeover is **not** production WhatsApp behaviour (spec v2: human sends every message).
- Don’t expose the server to the internet; no auth in this demo.
