"""
SQLite storage. Raw screenshots are never written to disk; only the verdict,
signals and (depending on sharing level) the message text are kept.

Schema is additive: older databases are migrated in place on first open.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional

DB_PATH = os.environ.get(
    "SAFECIRCLE_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "safecircle.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created REAL, lang TEXT, input_type TEXT, text TEXT,
  risk TEXT, category TEXT, signals TEXT, entities TEXT,
  ai_used INTEGER, ai_note TEXT, needs_review INTEGER,
  asked_family INTEGER DEFAULT 0, reported INTEGER DEFAULT 0,
  stage TEXT DEFAULT 'contact',
  severity TEXT DEFAULT 'none',
  imminence TEXT DEFAULT 'days',
  scam_probability REAL DEFAULT 0,
  review_flag INTEGER DEFAULT 0,
  override_by TEXT DEFAULT '',
  override_note TEXT DEFAULT '',
  policy_version TEXT DEFAULT '2.0',
  last_warned_at REAL DEFAULT 0,
  nudge_due_at REAL DEFAULT 0,
  emergency_due_at REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER, created REAL, reason TEXT, handled INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reported_entities (
  key_hash TEXT PRIMARY KEY, kind TEXT, count INTEGER, first_seen REAL
);
CREATE TABLE IF NOT EXISTS case_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id TEXT UNIQUE,
  case_id INTEGER,
  role TEXT,
  text TEXT,
  created REAL
);
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER,
  fact TEXT,
  value INTEGER,
  source TEXT,
  message_id TEXT,
  quote TEXT,
  recorded_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER,
  item_id TEXT,
  rules TEXT,
  ml TEXT,
  detection TEXT,
  judge TEXT,
  severity_before TEXT,
  severity_after TEXT,
  action TEXT,
  policy_version TEXT,
  created REAL
);
"""

CASE_COLUMNS = {
    "stage": "TEXT DEFAULT 'contact'",
    "severity": "TEXT DEFAULT 'none'",
    "imminence": "TEXT DEFAULT 'days'",
    "scam_probability": "REAL DEFAULT 0",
    "review_flag": "INTEGER DEFAULT 0",
    "override_by": "TEXT DEFAULT ''",
    "override_note": "TEXT DEFAULT ''",
    "policy_version": "TEXT DEFAULT '2.0'",
    "last_warned_at": "REAL DEFAULT 0",
    "nudge_due_at": "REAL DEFAULT 0",
    "emergency_due_at": "REAL DEFAULT 0",
}

DEFAULT_SETTINGS = {
    "elder_name": "Asha",
    "guardian_name": "Rohan",
    "guardian_phone": "+91 98xxxxxx21",
    "sharing_level": "auto_red",  # ask_only | auto_red | full
    "emergency_alerts": "1",
}

_lock = threading.Lock()
_conn = None


def conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _migrate(_conn)
        for k, v in DEFAULT_SETTINGS.items():
            _conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        _conn.commit()
    return _conn


def _migrate(c):
    existing = {r[1] for r in c.execute("PRAGMA table_info(cases)").fetchall()}
    for col, decl in CASE_COLUMNS.items():
        if col not in existing:
            c.execute(f"ALTER TABLE cases ADD COLUMN {col} {decl}")


def get_settings():
    with _lock:
        return {r["key"]: r["value"] for r in conn().execute("SELECT key, value FROM settings")}


def update_settings(values: dict):
    allowed = set(DEFAULT_SETTINGS)
    with _lock:
        for k, v in values.items():
            if k not in allowed:
                continue
            if not isinstance(v, (str, int, bool)):
                continue
            v = str(v).strip()[:80]
            if k == "sharing_level" and v not in ("ask_only", "auto_red", "full"):
                continue
            if k == "emergency_alerts":
                v = "1" if v in ("1", "true", "True", "yes", "on") else "0"
            conn().execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, v))
        conn().commit()


def save_case(**c):
    with _lock:
        cur = conn().execute(
            "INSERT INTO cases (created, lang, input_type, text, risk, category, signals, entities,"
            " ai_used, ai_note, needs_review, stage, severity, imminence, scam_probability,"
            " review_flag, policy_version, last_warned_at, nudge_due_at, emergency_due_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                time.time(),
                c["lang"],
                c["input_type"],
                c["text"],
                c["risk"],
                c["category"],
                json.dumps(sorted(c["signals"])),
                json.dumps(c["entities"]),
                int(c["ai_used"]),
                c.get("ai_note", ""),
                int(c.get("needs_review", False)),
                c.get("stage", "contact"),
                c.get("severity", "none"),
                c.get("imminence", "days"),
                float(c.get("scam_probability", 0) or 0),
                int(c.get("review_flag", False)),
                c.get("policy_version", "2.0"),
                float(c.get("last_warned_at", 0) or 0),
                float(c.get("nudge_due_at", 0) or 0),
                float(c.get("emergency_due_at", 0) or 0),
            ),
        )
        conn().commit()
        return cur.lastrowid


def update_case(case_id: int, **fields):
    allowed = {
        "risk", "category", "signals", "entities", "ai_used", "ai_note", "needs_review",
        "stage", "severity", "imminence", "scam_probability", "review_flag",
        "override_by", "override_note", "policy_version", "text",
        "last_warned_at", "nudge_due_at", "emergency_due_at", "asked_family", "reported",
    }
    cols, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("signals", "entities") and not isinstance(v, str):
            v = json.dumps(sorted(v) if k == "signals" else v)
        if k in ("ai_used", "needs_review", "review_flag", "asked_family", "reported"):
            v = int(bool(v))
        cols.append(f"{k} = ?")
        vals.append(v)
    if not cols:
        return
    vals.append(case_id)
    with _lock:
        conn().execute(f"UPDATE cases SET {', '.join(cols)} WHERE id = ?", vals)
        conn().commit()


def get_case(case_id):
    with _lock:
        row = conn().execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return _case_dict(row) if row else None


def _case_dict(row):
    d = dict(row)
    d["signals"] = json.loads(d["signals"] or "[]")
    d["entities"] = json.loads(d["entities"] or "{}")
    d["review_flag"] = bool(d.get("review_flag") or d.get("needs_review"))
    return d


def list_cases(since=None):
    q, args = "SELECT * FROM cases", ()
    if since:
        q, args = q + " WHERE created >= ?", (since,)
    with _lock:
        rows = conn().execute(q + " ORDER BY created DESC LIMIT 200", args).fetchall()
    return [_case_dict(r) for r in rows]


def mark_case(case_id, field):
    if field not in ("asked_family", "reported"):
        raise ValueError(field)
    with _lock:
        conn().execute(f"UPDATE cases SET {field} = 1 WHERE id = ?", (case_id,))
        conn().commit()


def next_message_id(case_id: int) -> str:
    with _lock:
        n = conn().execute(
            "SELECT COUNT(*) AS n FROM case_items WHERE case_id = ?", (case_id,)
        ).fetchone()["n"]
    return f"m_{case_id}_{n + 1:04d}"


def add_item(case_id: int, role: str, text: str, message_id: str = None) -> str:
    mid = message_id or next_message_id(case_id)
    with _lock:
        conn().execute(
            "INSERT INTO case_items (message_id, case_id, role, text, created) VALUES (?,?,?,?,?)",
            (mid, case_id, role, text, time.time()),
        )
        conn().commit()
    return mid


def list_items(case_id: int) -> list[dict]:
    with _lock:
        rows = conn().execute(
            "SELECT * FROM case_items WHERE case_id = ? ORDER BY id ASC", (case_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def append_fact(
    case_id: int,
    fact: str,
    *,
    value: bool = True,
    source: str = "rules",
    message_id: str = "",
    quote: str = "",
) -> bool:
    """Append a fact if not already true for this case. Returns True if newly recorded."""
    with _lock:
        existing = conn().execute(
            "SELECT 1 FROM facts WHERE case_id = ? AND fact = ? AND value = 1 LIMIT 1",
            (case_id, fact),
        ).fetchone()
        if existing:
            return False
        from datetime import datetime, timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        recorded = datetime.now(ist).isoformat(timespec="seconds")
        conn().execute(
            "INSERT INTO facts (case_id, fact, value, source, message_id, quote, recorded_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (case_id, fact, int(bool(value)), source, message_id, quote[:200], recorded),
        )
        conn().commit()
    return True


def list_facts(case_id: int) -> list[dict]:
    with _lock:
        rows = conn().execute(
            "SELECT * FROM facts WHERE case_id = ? ORDER BY id ASC", (case_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def fact_names(case_id: int) -> set[str]:
    return {f["fact"] for f in list_facts(case_id) if f.get("value")}


def add_audit(
    case_id: int,
    *,
    item_id: str = "",
    rules: Any = None,
    ml: Any = None,
    detection: Any = None,
    judge: Any = None,
    severity_before: str = "",
    severity_after: str = "",
    action: str = "",
    policy_version: str = "2.0",
):
    with _lock:
        conn().execute(
            "INSERT INTO audit_log (case_id, item_id, rules, ml, detection, judge,"
            " severity_before, severity_after, action, policy_version, created)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                case_id,
                item_id,
                json.dumps(rules or {}, default=list),
                json.dumps(ml or {}, default=list),
                json.dumps(detection or {}, default=list),
                json.dumps(judge or {}, default=list),
                severity_before,
                severity_after,
                action,
                policy_version,
                time.time(),
            ),
        )
        conn().commit()


def list_audit(case_id: int) -> list[dict]:
    with _lock:
        rows = conn().execute(
            "SELECT * FROM audit_log WHERE case_id = ? ORDER BY id ASC", (case_id,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("rules", "ml", "detection", "judge"):
            try:
                d[k] = json.loads(d[k] or "{}")
            except json.JSONDecodeError:
                d[k] = {}
        out.append(d)
    return out


def add_alert(case_id, reason):
    """One alert per case. 'asked' outranks auto reasons and re-opens handled alerts."""
    rank = {"auto_high": 1, "nudge": 2, "emergency": 3, "asked": 4}
    with _lock:
        existing = conn().execute(
            "SELECT id, reason FROM alerts WHERE case_id = ?", (case_id,)
        ).fetchone()
        if existing:
            if rank.get(reason, 0) > rank.get(existing["reason"], 0):
                conn().execute(
                    "UPDATE alerts SET reason = ?, handled = 0, created = ? WHERE id = ?",
                    (reason, time.time(), existing["id"]),
                )
                conn().commit()
            elif reason == "asked" and existing["reason"] != "asked":
                conn().execute(
                    "UPDATE alerts SET reason = 'asked', handled = 0, created = ? WHERE id = ?",
                    (time.time(), existing["id"]),
                )
                conn().commit()
            return existing["id"]
        cur = conn().execute(
            "INSERT INTO alerts (case_id, created, reason) VALUES (?,?,?)",
            (case_id, time.time(), reason),
        )
        conn().commit()
        return cur.lastrowid


def list_alerts():
    with _lock:
        rows = conn().execute(
            "SELECT * FROM alerts ORDER BY created DESC LIMIT 100"
        ).fetchall()
    return [dict(r) for r in rows]


def handle_alert(alert_id):
    with _lock:
        conn().execute("UPDATE alerts SET handled = 1 WHERE id = ?", (alert_id,))
        conn().commit()


def due_cases(now: float = None) -> list[dict]:
    now = now if now is not None else time.time()
    with _lock:
        rows = conn().execute(
            "SELECT * FROM cases WHERE"
            " (nudge_due_at > 0 AND nudge_due_at <= ?)"
            " OR (emergency_due_at > 0 AND emergency_due_at <= ?)",
            (now, now),
        ).fetchall()
    return [_case_dict(r) for r in rows]


def _hash(kind, value):
    return hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()


def report_entities(keys):
    with _lock:
        for kind, value in keys:
            h = _hash(kind, value)
            conn().execute(
                "INSERT INTO reported_entities VALUES (?,?,1,?) "
                "ON CONFLICT(key_hash) DO UPDATE SET count = count + 1",
                (h, kind, time.time()),
            )
        conn().commit()


def any_reported(keys):
    if not keys:
        return False
    hashes = [_hash(k, v) for k, v in keys]
    with _lock:
        q = "SELECT 1 FROM reported_entities WHERE key_hash IN (%s) LIMIT 1" % ",".join(
            "?" * len(hashes)
        )
        return conn().execute(q, hashes).fetchone() is not None


def reset():
    with _lock:
        c = conn()
        for t in ("cases", "alerts", "reported_entities", "settings", "case_items", "facts", "audit_log"):
            try:
                c.execute(f"DELETE FROM {t}")
            except sqlite3.OperationalError:
                pass
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT INTO settings VALUES (?, ?)", (k, v))
        c.commit()
