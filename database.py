# database.py — ExamGuard v3 — All DB operations

import sqlite3
from datetime import datetime

import security
from config import DB_FILE


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def initialize_db():
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name     TEXT    NOT NULL,
            student_id       TEXT    NOT NULL,
            pc_hostname      TEXT,
            start_time       TEXT,
            end_time         TEXT,
            total_keystrokes INTEGER DEFAULT 0,
            session_hash     TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id       INTEGER NOT NULL,
            event_type       TEXT    NOT NULL,
            detail           TEXT,
            timestamp        TEXT,
            integrity_hash   TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS access_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            action    TEXT    NOT NULL,
            detail    TEXT
        );
    """)
    con.commit()
    con.close()


# ── Encrypted event types ─────────────────────────────────────
_ENCRYPT_TYPES = {
    "clipboard_change", "screenshot", "file_copy",
    "usb_insert",       "file_access", "ide_preexisting",
}


# ── Sessions ──────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _session_canonical(name, sid, hostname, start) -> str:
    return f"{name}|{sid}|{hostname}|{start}"


def create_session(student_name: str, student_id: str, pc_hostname: str) -> int:
    now = _now()
    con = _conn()
    cur = con.execute(
        "INSERT INTO sessions (student_name, student_id, pc_hostname, start_time, session_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        (student_name, student_id, pc_hostname, now,
         security.sign(_session_canonical(student_name, student_id, pc_hostname, now)))
    )
    sid = cur.lastrowid
    con.commit()
    con.close()
    return sid


def end_session(session_id: int):
    con = _conn()
    con.execute("UPDATE sessions SET end_time=? WHERE id=?", (_now(), session_id))
    con.commit()
    con.close()


def update_keystroke_count(session_id: int, count: int):
    con = _conn()
    con.execute("UPDATE sessions SET total_keystrokes=? WHERE id=?", (count, session_id))
    con.commit()
    con.close()


def get_session(session_id: int) -> dict | None:
    con = _conn()
    row = con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_all_sessions() -> list[dict]:
    con = _conn()
    rows = con.execute("SELECT * FROM sessions ORDER BY start_time DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]


def delete_session(session_id: int):
    con = _conn()
    con.execute("DELETE FROM events   WHERE session_id=?", (session_id,))
    con.execute("DELETE FROM sessions WHERE id=?",         (session_id,))
    con.commit()
    con.close()


def delete_old_sessions(days: int = 30):
    con = _conn()
    con.execute(
        "DELETE FROM events WHERE session_id IN "
        "(SELECT id FROM sessions WHERE start_time < date('now',?))",
        (f"-{days} days",))
    con.execute(
        "DELETE FROM sessions WHERE start_time < date('now',?)",
        (f"-{days} days",))
    con.commit()
    con.close()


def get_sessions_with_stats() -> list[dict]:
    con = _conn()
    rows = con.execute("""
        SELECT
            s.id, s.student_name, s.student_id, s.pc_hostname,
            s.start_time, s.end_time, s.total_keystrokes,
            COALESCE(SUM(CASE WHEN e.event_type='window_switch'    THEN 1 ELSE 0 END),0) AS window_switches,
            COALESCE(SUM(CASE WHEN e.event_type='clipboard_change' THEN 1 ELSE 0 END),0) AS clipboard_events,
            COALESCE(SUM(CASE WHEN e.event_type='file_copy'        THEN 1 ELSE 0 END),0) AS file_copies,
            COALESCE(SUM(CASE WHEN e.event_type='screenshot'       THEN 1 ELSE 0 END),0) AS screenshots,
            COALESCE(SUM(CASE WHEN e.event_type='usb_insert'       THEN 1 ELSE 0 END),0) AS usb_inserts,
            COALESCE(SUM(CASE WHEN e.event_type='file_access'      THEN 1 ELSE 0 END),0) AS file_accesses,
            COALESCE(SUM(CASE WHEN e.event_type='ide_preexisting'  THEN 1 ELSE 0 END),0) AS ide_preexisting
        FROM sessions s
        LEFT JOIN events e ON s.id = e.session_id
        GROUP BY s.id
        ORDER BY s.start_time DESC
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Events ────────────────────────────────────────────────────

def log_event(session_id: int, event_type: str, detail: str):
    now = _now()
    stored = security.encrypt(detail) if event_type in _ENCRYPT_TYPES else detail
    canonical = security.event_canonical(session_id, event_type, stored, now)
    sig = security.sign(canonical)
    con = _conn()
    con.execute(
        "INSERT INTO events (session_id, event_type, detail, timestamp, integrity_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        (session_id, event_type, stored, now, sig))
    con.commit()
    con.close()


def get_events_for_session(session_id: int,
                           decrypt_sensitive: bool = False) -> list[dict]:
    con = _conn()
    rows = con.execute(
        "SELECT * FROM events WHERE session_id=? ORDER BY timestamp ASC",
        (session_id,)).fetchall()
    con.close()

    result = []
    for row in rows:
        ev = dict(row)
        canonical = security.event_canonical(
            ev["session_id"], ev["event_type"],
            ev["detail"] or "", ev["timestamp"] or "")
        ev["tampered"] = not security.verify(canonical, ev.get("integrity_hash", ""))

        if decrypt_sensitive and ev["event_type"] in _ENCRYPT_TYPES:
            ev["detail_plain"] = security.decrypt(ev["detail"] or "")
        else:
            ev["detail_plain"] = ev["detail"]
        result.append(ev)
    return result


def get_event_counts(session_id: int) -> dict:
    con = _conn()
    rows = con.execute(
        "SELECT event_type, COUNT(*) as cnt FROM events WHERE session_id=? GROUP BY event_type",
        (session_id,)).fetchall()
    con.close()
    return {r["event_type"]: r["cnt"] for r in rows}


# ── Access log ────────────────────────────────────────────────

def log_access(action: str, detail: str = ""):
    con = _conn()
    con.execute(
        "INSERT INTO access_log (timestamp, action, detail) VALUES (?, ?, ?)",
        (_now(), action, detail))
    con.commit()
    con.close()


def get_access_log(limit: int = 100) -> list[dict]:
    con = _conn()
    rows = con.execute(
        "SELECT * FROM access_log ORDER BY timestamp DESC LIMIT ?",
        (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]
