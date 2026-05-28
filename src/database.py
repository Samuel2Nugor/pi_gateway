import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.logger import get_logger

log = get_logger("database")

DB_PATH = Path("data/gateway.db")

# Thread-local connections so each thread gets its own SQLite connection
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db() -> None:
    """Create tables if they don't exist. Call once at startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_id INTEGER,
            received_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            final_price REAL NOT NULL,
            raw_payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        );
    """)
    conn.commit()
    log.info("Database initialised at %s", DB_PATH)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Messages

def insert_message(command_id: int, topic: str, tag_id: int, title: str,
                   final_price: float, raw_payload: str) -> int:
    """Insert an inbound message and return its row id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO messages
            (command_id, received_at, topic, tag_id, title, final_price, raw_payload, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (command_id, _now(), topic, tag_id, title, final_price, raw_payload),
    )
    conn.commit()
    log.debug("Inserted message id=%d tag_id=%s status=pending", cur.lastrowid, tag_id)
    return cur.lastrowid


def update_message_status(message_id: int, status: str) -> None:
    """Update the status of a message. Valid: pending, processing, acked, failed."""
    conn = _get_conn()
    conn.execute(
        "UPDATE messages SET status = ? WHERE id = ?",
        (status, message_id),
    )
    conn.commit()
    log.debug("Updated message id=%d status=%s", message_id, status)


def load_unfinished_messages() -> list[dict]:
    """
    Load unfinished messages after gateway restart.
    Pending or processing messages can be retried.
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, command_id, tag_id, raw_payload FROM messages
            WHERE status IN ('pending', 'processing')
            ORDER BY id""",
    ).fetchall()

    msgs = [
        {
            "id": r["id"],
            "command_id": r["command_id"],
            "tag_id": r["tag_id"],
            "payload": r["raw_payload"],
        }
        for r in rows
    ]
    if msgs:
        log.info("Loaded %d unfinished message(s) from gateway.db", len(msgs))
    return msgs
