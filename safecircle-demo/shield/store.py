"""
SQLite storage. Raw screenshots are never written to disk; only the verdict,
signals and (depending on sharing level) the message text are kept.
"""
import hashlib
import json
import os
import sqlite3
import threading
import time

DB_PATH = os.environ.get("SAFECIRCLE_DB", os.path.join(os.path.dirname(__file__), "..", "data", "safecircle.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created REAL, lang TEXT, input_type TEXT, text TEXT,
  risk TEXT, category TEXT, signals TEXT, entities TEXT,
  ai_used INTEGER, ai_note TEXT, needs_review INTEGER,
  asked_family INTEGER DEFAULT 0, reported INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER, created REAL, reason TEXT, handled INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reported_entities (
  key_hash TEXT PRIMARY KEY, kind TEXT, count INTEGER, first_seen REAL
);
"""

DEFAULT_SETTINGS = {
    "elder_name": "Asha",
    "guardian_name": "Rohan",
    "guardian_phone": "+91 98xxxxxx21",
    "sharing_level": "auto_red",  # ask_only | auto_red | full
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
        for k, v in DEFAULT_SETTINGS.items():
            _conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
        _conn.commit()
    return _conn


def get_settings():
    with _lock:
        return {r["key"]: r["value"] for r in conn().execute("SELECT key, value FROM settings")}


def update_settings(values: dict):
    allowed = set(DEFAULT_SETTINGS)
    with _lock:
        for k, v in values.items():
            if k in allowed and isinstance(v, str):
                if k == "sharing_level" and v not in ("ask_only", "auto_red", "full"):
                    continue
                conn().execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, v.strip()[:80]))
        conn().commit()


def save_case(**c):
    with _lock:
        cur = conn().execute(
            "INSERT INTO cases (created, lang, input_type, text, risk, category, signals, entities, ai_used, ai_note, needs_review)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), c["lang"], c["input_type"], c["text"], c["risk"], c["category"],
             json.dumps(sorted(c["signals"])), json.dumps(c["entities"]), int(c["ai_used"]),
             c.get("ai_note", ""), int(c.get("needs_review", False))),
        )
        conn().commit()
        return cur.lastrowid


def get_case(case_id):
    with _lock:
        row = conn().execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return _case_dict(row) if row else None


def _case_dict(row):
    d = dict(row)
    d["signals"] = json.loads(d["signals"])
    d["entities"] = json.loads(d["entities"])
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


def add_alert(case_id, reason):
    with _lock:
        # One alert per case. "asked" (the elder asked for help) outranks "auto_high"
        # and re-opens the alert if the family had already marked it handled.
        existing = conn().execute("SELECT id, reason FROM alerts WHERE case_id = ?", (case_id,)).fetchone()
        if existing:
            if reason == "asked" and existing["reason"] != "asked":
                conn().execute("UPDATE alerts SET reason = 'asked', handled = 0, created = ? WHERE id = ?",
                               (time.time(), existing["id"]))
                conn().commit()
            return existing["id"]
        cur = conn().execute("INSERT INTO alerts (case_id, created, reason) VALUES (?,?,?)", (case_id, time.time(), reason))
        conn().commit()
        return cur.lastrowid


def list_alerts():
    with _lock:
        rows = conn().execute("SELECT * FROM alerts ORDER BY created DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


def handle_alert(alert_id):
    with _lock:
        conn().execute("UPDATE alerts SET handled = 1 WHERE id = ?", (alert_id,))
        conn().commit()


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
        q = "SELECT 1 FROM reported_entities WHERE key_hash IN (%s) LIMIT 1" % ",".join("?" * len(hashes))
        return conn().execute(q, hashes).fetchone() is not None


def reset():
    with _lock:
        c = conn()
        for t in ("cases", "alerts", "reported_entities", "settings"):
            c.execute(f"DELETE FROM {t}")
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT INTO settings VALUES (?, ?)", (k, v))
        c.commit()
