import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from logger import get_logger

log = get_logger("database")

DB_PATH = Path("gateway.db")

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
    
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT    NOT NULL,
            topic       TEXT    NOT NULL,
            tag_id      TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            final_price TEXT    NOT NULL,
            raw_payload TEXT    NOT NULL
        );
            
        CREATE TABLE IF NOT EXISTS ble_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id   INTEGER NOT NULL REFERENCES messages(id),
            completed_at TEXT    NOT NULL,
            ack          TEXT    NOT NULL,
            reason       TEXT,
            attempts 	 INTEGER NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS retry_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id  INTEGER NOT NULL REFERENCES messages(id),
            attempt     INTEGER NOT NULL,
            attempt_at  TEXT    NOT NULL,
            ack         TEXT    NOT NULL,
            reason      TEXT
        );
    """)
    
    conn.commit()
    log.info("Database initialised at %s", DB_PATH)
    
    
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
    

def insert_message(topic: str, tag_id: str, title: str, final_price: str, raw_payload: str) -> int:
    """Insert an inbound message and return its row id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO messages (received_at, topic, tag_id, title, final_price, raw_payload)
            VALUES (?, ? , ?, ?, ?, ?)""",
        (_now(), topic, tag_id, title, final_price, raw_payload),
    )
    
    conn.commit()
    log.debug("Inserted message id=%d tag_id=%s", cur.lastrowid, tag_id)
    return cur.lastrowid
    

def insert_ble_result(message_id: int, ack: str, reason: Optional[str], attempts: int) -> None:
    """Insert the final BLE outcome for a message."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO ble_results (message_id, completed_at, ack, reason, attempts)
            VALUES (?, ?, ?, ?, ?)""",
        (message_id, _now(), ack, reason, attempts),
    )
    conn.commit()
    log.debug("Inserted ble_result message_id=%d ack=%s reason=%s", message_id, ack, reason)
    
    
def insert_retry(message_id: int, attempt: int, ack: str, reason: Optional[str]) -> None:
    """Insert a single retry attempt record"""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO retry_history
			(message_id, attempt, attempt_at, ack, reason)
            VALUES (?, ?, ?, ?, ?)""",
        (message_id, attempt, _now(), ack, reason),
    )
    conn.commit()
    log.debug("Inserted retry message_id=%d attempt=%d reason=%s", message_id, attempt, reason)
    
            
            
