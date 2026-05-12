import asyncio
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from logger import get_logger

log = get_logger("queue_manager")

QUEUE_DB_PATH = Path("queue.db")
TAG_THROTTLE_SECONDS = 2.0   # minimum gap between writes to the same tag

# Data model
@dataclass
class QueuedMessage:
    tag_id: str
    payload: str
    enqueued_at: float = field(default_factory=time.monotonic)
    message_id: Optional[int] = None  # databse row_id, set after insert_message()
    

# Persistence (SQLite-backed queue for restart survival)
def _get_queue_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(QUEUE_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_id      TEXT    NOT NULL,
            payload     TEXT    NOT NULL,
            message_id  INTEGER,
            enqueued_at REAL    NOT NULL
        )
    """)
    conn.commit()
    return conn
    
def persist_message(msg: QueuedMessage) -> int:
    """Save a message to the persistent queue. returns the queue row id."""
    conn = _get_queue_conn()
    cur = conn.execute(
        "INSERT INTO pending_queue (tag_id, payload, message_id, enqueued_at) VALUES (?, ?, ?, ?)",
        (msg.tag_id, msg.payload, msg.message_id, msg.enqueued_at),
    )
    conn.commit()
    conn.close()
    log.debug("Persisted queue entry id=%d tag_id=%s", cur.lastrowid, msg.tag_id)
    return cur.lastrowid
    
    
def load_persisted_messages() -> list[QueuedMessage]:
    """Load any messages that survived a restart."""
    conn = _get_queue_conn()
    rows = conn.execute(
        "SELECT tag_id, payload, message_id, enqueued_at FROM pending_queue ORDER by id"
    ).fetchall()
    conn.close()    
    msgs = [QueuedMessage(tag_id=r[0], payload=r[1],
                        message_id=r[2], enqueued_at=r[3]) for r in rows]
    if msgs:
        log.info("Loaded %d persisted message(s) from queue.db", len(msgs))
    return msgs
    
    
def clear_persisted_queue() -> None:
    conn = _get_queue_conn()
    conn.execute("DELETE FROM pending_queue")
    conn.commit()
    conn.close()
    log.debug("Cleared persistent queue")
    
    
# Queue manager
class QueueManager:
    """Thread-safe BLE write queue with:
    - Async in-memory queue
    - SQLite persistence across restarts
    - per-tag throttling
    """
    
    def __init__(self, ble_write_fn: Callable[[str, int], dict],
                throttle_seconds: float = TAG_THROTTLE_SECONDS) -> None:
        self._ble_write = ble_write_fn
        self._throttle = throttle_seconds
        self._queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()
        self._last_write: dict[str, float] = {}   #tag_id -> last write timestamp
        self._lock = threading.Lock()
        self._running = False
        #self._on_result = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_result: Optional[Callable[[QueuedMessage, dict], None]] = None
        #self._loop: asyncio.AbstractEventLoop | None = None
    
    def set_result_callback(self, fn: Callable[[QueuedMessage, dict], None]) -> None:
        """Optional callback invoked with (message, ble_result) after each write"""
        self._on_result = fn
        
    def enqueue(self,msg: QueuedMessage) -> None:
        """Add a message to the queue and persist it."""
        persist_message(msg)
        if self._loop is not None and self._loop.is_running():
            # Called from MQTT thread - schedule into the event loop safely
            self._loop.call_soon_threadsafe(lambda: self._queue.put_nowait(msg))
        else:
            self._queue.put_nowait(msg)
        log.info("[QUEUE] Enqueue tag_id=%s", msg.tag_id)
        #if self._loop is None:
            #log.error( "[QUEUE] Cannot enqueue: event loop not ready")
            #return
            
        #self._loop.call_soon_threadsafe(self._enqueue_inside_loop, msg)
        
    #def _enqueue_inside_loop(self, msg: QueuedMessage) -> None:
        #"""Runs inside asyncio event loop thread."""
        #persist_message(msg)
        #self._queue.put_nowait(msg)
        #log.info("[QUEUE] Enqueue tag_id=%s queue_size=%d", msg.tag_id, self._queue.qsize())
        
    async def start(self) -> None:
        """Load persisted messages then start processing loop."""
        #self._loop = asyncio.get_running_loop()
        self._running = True
        
        # Lear FIRST then load - prevents double-persist on stop()
        persisted = load_persisted_messages()
        clear_persisted_queue()
        for msg in persisted:
            self._queue.put_nowait(msg)
            log.info("[QUEUE] Reloaded tag_id=%s from persistance", msg.tag_id)
        #clear_persisted_queue()
        
        
        # Store event loop reference so enqueue() can wake it from other threads
        self._loop = asyncio.get_running_loop()
        log.info("[QUEUE] Queue manager started")
        await self._process_loop()
        
    async def stop(self) -> None:
        """Graceful shutdown - persists any remaining messages."""
        self._running = False
        remaining = []
        while not self._queue.empty():
            try:
                remaining.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
                
        for msg in remaining:
            persist_message(msg)
        log.info("[QUEUE] Stopped. Persisted %d remining message(s).", len(remaining))
        
    
    async def _process_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
                
            await self._throttle_tag(msg.tag_id)
            
            log.info("[QUEUE] Processing tag_id=%s", msg.tag_id)
            
            #Pass both payload and message_id to the write function
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._ble_write, msg.payload, msg.message_id
            )
            
            log.info("[QUEUE] Result tag_id=%s ack=%s reason=%s",
                    msg.tag_id, result.get("ack"), result.get("reason"))
                    
            with self._lock:
                self._last_write[msg.tag_id] = time.monotonic()
                
            if self._on_result:
                self._on_result(msg, result)
                
            self._queue.task_done()
            
    
    async def _throttle_tag(self, tag_id: str) -> None:
        with self._lock:
            last = self._last_write.get(tag_id)
        if last is not None:
            elapsed = time.monotonic() - last
            wait = self._throttle - elapsed
            if wait > 0:
                log.debug("[QUEUE] Throttling tag_id=%s for %.1fs", tag_id, wait)
                await asyncio.sleep(wait)
            
            
            
    
    
    
    
