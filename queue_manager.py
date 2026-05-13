import asyncio
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from logger import get_logger

log = get_logger("queue_manager")

TAG_THROTTLE_SECONDS = 2.0   # minimum gap between writes to the same tag

# Data model
@dataclass
class QueuedMessage:
    tag_id: str
    payload: str
    message_id: Optional[int] = None 
    enqueued_at: float = field(default_factory=time.monotonic)
    
    
    
# Queue manager
class QueueManager:
    """Thread-safe BLE write queue with:
    - Async in-memory queue
    - Restart recovery via gateway.db
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_result: Optional[Callable[[QueuedMessage, dict], None]] = None
    
    def set_result_callback(self, fn: Callable[[QueuedMessage, dict], None]) -> None:
        """Optional callback invoked with (message, ble_result) after each write"""
        self._on_result = fn
        
    def enqueue(self, msg: QueuedMessage) -> None:
        """Add a message to the in-memory queue. Thread-safe"""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(lambda: self._queue.put_nowait(msg))
        else:
            self._queue.put_nowait(msg)
        log.info("[QUEUE] Enqueue tag_id=%s", msg.tag_id)
       
    async def start(self) -> None:
        """Reload unfinished messages from gateway.db then start processing and loop."""
        from database import load_unfinished_messages, update_message_status
        
        self._running = True
        self._loop = asyncio.get_running_loop()
        
        # Reload any messages that didnt dfinish before last shutdown
        unfinished = load_unfinished_messages()
        for row in unfinished:
            # Reset to pending in case they were stuck as 'processing'
            update_message_status(row["id"], "pending")
            self._queue.put_nowait(QueuedMessage(
                tag_id=row["tag_id"],
                payload=row["payload"],
                message_id=row["id"],
            ))
            log.info("[QUEUE] Reloaded message_id=%d tag_id=%s", row["id"], row["tag_id"])
            
        log.info("[QUEUE] Queue manager started")
        await self._process_loop()
        
    async def stop(self) -> None:
        """Graceful shutdown - unfinished messages stay as 'pending' in gateway.db."""
        from database import update_message_status
        
        self._running = False
        remaining = 0
        while not self._queue.empty():
            try:
                msg = self._queue.get_nowait()
                if msg.message_id is not None:
                    update_message_status(msg.message_id, "pending")
                remaining += 1
            except asyncio.QueueEmpty:
                break
        log.info("[QUEUE] Stopped. %d message(s) left as pending in gateway.db.", remaining)
        
    
    async def _process_loop(self) -> None:
        from database import update_message_status
        
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
                
            await self._throttle_tag(msg.tag_id)
            
            # Mark as processing
            if msg.message_id is not None:
                update_message_status(msg.message_id, "processing")
            
            log.info("[QUEUE] Processing tag_id=%s message_id=%s", msg.tag_id, msg.message_id)
            
            #Pass both payload and message_id to the write function
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._ble_write, msg.payload, msg.message_id
            )
            
            log.info("[QUEUE] Result tag_id=%s ack=%s reason=%s",
                    msg.tag_id, result.get("ack"), result.get("reason"))
                    
            # Update final status in gateway.db
            if msg.message_id is not None:
                status = "sent" if result.get("ack") == "true" else "failed"
                update_message_status(msg.message_id, status)
                    
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
