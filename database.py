# database.py — ExamGuard v4.1 — All DB operations

"""
PERFORMANCE FIXES (v4.1):
  - Module-level SQLite connection with WAL mode (replaces per-call open/close)
  - threading.Lock() guards all write operations
  - Connection uses check_same_thread=False (safe with the write lock)
  - Lazy initialization pattern for thread safety at startup
"""

import sqlite3
import threading
import logging
from datetime import datetime

import security
from config import DB_FILE

logger = logging.getLogger("examguard.database")

# ─────────────────────────────────────────────────────────────
#  Connection pool (single persistent WAL connection + write lock)
# ─────────────────────────────────────────────────────────────

_db_conn:   "sqlite3.Connection | None" = None
_db_lock    = threading.Lock()
_init_done  = False


def _get_conn() -> sqlite3.Connection:
    """Return the module-level connection, creating it if needed."""
    global _db_conn
    if _db_conn is None:
        with _db_lock:
            if _db_conn is None:  # double-checked locking
                conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL
                conn.execute("PRAGMA cache_size=-8000")    # 8MB page cache
                _db_conn = conn
    return _db_conn


def _execute_read(sql: str, params: tuple = ()) -> list:
    """Execute a SELECT and return rows. Reads don't need the write lock."""
    conn = _get_conn()
    with _db_lock:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def _execute_write(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE. Returns lastrowid or rowcount."""
    conn = _get_conn()
    with _db_lock:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def _execute_script(sql: str):
    """Execute a multi-statement script (used only for schema creation)."""
    conn = _get_conn()
    with _db_lock:
        conn.executescript(sql)
        conn.commit()


# ─────────────────────────────────────────────────────────────
#  Schema
# ─────────────────────────────────────────────────────────────

def initialize_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    global _init_done
    if _init_done:
        return
    _execute_script("""
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

        CREATE INDEX IF NOT EXISTS idx_events_session
            ON events(session_id, event_type);
        CREATE INDEX IF NOT EXISTS idx_sessions_start
            ON sessions(start_time DESC);
    """)
    _init_done = True


# ─────────────────────────────────────────────────────────────
#  Encrypted event types
# ─────────────────────────────────────────────────────────────

_ENCRYPT_TYPES = {
    "clipboard_change", "screenshot", "file_copy",
    "usb_insert",       "file_access", "ide_preexisting",
}


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _session_canonical(name, sid, hostname, start) -> str:
    return f"{name}|{sid}|{hostname}|{start}"


# ─────────────────────────────────────────────────────────────
#  Sessions
# ─────────────────────────────────────────────────────────────

def create_session(student_name: str, student_id: str, pc_hostname: str) -> int:
    now = _now()
    return _execute_write(
        "INSERT INTO sessions (student_name, student_id, pc_hostname, start_time, session_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        (student_name, student_id, pc_hostname, now,
         security.sign(_session_canonical(student_name, student_id, pc_hostname, now)))
    )


def end_session(session_id: int):
    _execute_write(
        "UPDATE sessions SET end_time=? WHERE id=?",
        (_now(), session_id)
    )


def update_keystroke_count(session_id: int, count: int):
    _execute_write(
        "UPDATE sessions SET total_keystrokes=? WHERE id=?",
        (count, session_id)
    )


def get_session(session_id: int) -> "dict | None":
    rows = _execute_read("SELECT * FROM sessions WHERE id=?", (session_id,))
    return dict(rows[0]) if rows else None


def get_all_sessions() -> list:
    rows = _execute_read("SELECT * FROM sessions ORDER BY start_time DESC")
    return [dict(r) for r in rows]


def delete_session(session_id: int):
    # Cascade deletes events automatically (FK ON DELETE CASCADE)
    _execute_write("DELETE FROM sessions WHERE id=?", (session_id,))


def delete_old_sessions(days: int = 30):
    cutoff = f"-{days} days"
    _execute_write(
        "DELETE FROM sessions WHERE start_time < date('now', ?)",
        (cutoff,)
    )


def get_sessions_with_stats() -> list:
    rows = _execute_read("""
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
    """)
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
#  Events
# ─────────────────────────────────────────────────────────────

def log_event(session_id: int, event_type: str, detail: str):
    now     = _now()
    stored  = security.encrypt(detail) if event_type in _ENCRYPT_TYPES else detail
    canonical = security.event_canonical(session_id, event_type, stored, now)
    sig     = security.sign(canonical)
    _execute_write(
        "INSERT INTO events (session_id, event_type, detail, timestamp, integrity_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        (session_id, event_type, stored, now, sig)
    )


def get_events_for_session(session_id: int,
                            decrypt_sensitive: bool = False) -> list:
    rows = _execute_read(
        "SELECT * FROM events WHERE session_id=? ORDER BY timestamp ASC",
        (session_id,)
    )

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
    rows = _execute_read(
        "SELECT event_type, COUNT(*) as cnt FROM events WHERE session_id=? GROUP BY event_type",
        (session_id,)
    )
    return {r["event_type"]: r["cnt"] for r in rows}


# ─────────────────────────────────────────────────────────────
#  Access log
# ─────────────────────────────────────────────────────────────

def log_access(action: str, detail: str = ""):
    _execute_write(
        "INSERT INTO access_log (timestamp, action, detail) VALUES (?, ?, ?)",
        (_now(), action, detail)
    )


def get_access_log(limit: int = 200) -> list:
    rows = _execute_read(
        "SELECT * FROM access_log ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    return [dict(r) for r in rows]
