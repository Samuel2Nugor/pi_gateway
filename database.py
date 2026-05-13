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
            raw_payload TEXT    NOT NULL,
            status		TEXT	NOT Null DEFAULT 'pending'
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

# Messages  

def insert_message(topic: str, tag_id: str, title: str, final_price: str, raw_payload: str) -> int:
    """Insert an inbound message and return its row id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO messages (received_at, topic, tag_id, title, final_price, raw_payload, status)
            VALUES (?, ? , ?, ?, ?, ?, 'pending')""",
        (_now(), topic, tag_id, title, final_price, raw_payload),
    )
    
    conn.commit()
    log.debug("Inserted message id=%d tag_id=%s status=pending", cur.lastrowid, tag_id)
    return cur.lastrowid
    
def update_message_status(message_id: int, status: str) -> None:
	"""Update the status of a message. Valid: pending, processing, sent, failed."""
	conn = _get_conn()
	conn.execute(
		"UPDATE messages SET status = ? WHERE id = ?",
		(status, message_id),
	)
	conn.commit()
	log.debug("Updated message id=%d status=%s", message_id, status)
	
def load_unfinished_messages() -> list[dict]:
	"""
	Load all messages with status 'pending' or 'processing' on startup.
	These need to be re-enqueued after a restart.
	"""
	conn = _get_conn()
	rows = conn.execute(
		"""SELECT id, tag_id, raw_payload FROM messages
			WHERE status IN ('pending', 'processing')
			ORDER BY id""",
	).fetchall()
	
	msgs = [{"id": r["id"], "tag_id": r["tag_id"], "payload": r["raw_payload"]} for r in rows]
	if msgs:
		log.info("Loaded %d unfinished messages(s) from gateway.db", len(msgs))
	return msgs
	
	
# BLE results

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
    
            
            
