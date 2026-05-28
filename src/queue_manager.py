import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.logger import get_logger

log = get_logger("queue_manager")

TAG_THROTTLE_SECONDS = 2.0   # minimum gap between writes to the same tag

# Data model
@dataclass
class QueuedMessage:
    command_id: int
    tag_id: int
    payload: str
    message_id: Optional[int] = None 
    enqueued_at: float = field(default_factory=time.monotonic)
    
    
    
# Queue manager
class QueueManager:
    """Thread-safe BLE write queue with:
    - Async in-memory queue
    - Restart recovery via gateway.db
    - Per-tag throttling
    """
    
    def __init__(self, ble_write_fn: Callable,
                throttle_seconds: float = TAG_THROTTLE_SECONDS) -> None:
        self._ble_write = ble_write_fn
        self._throttle = throttle_seconds
        self._queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()
        self._last_write: dict[int, float] = {}   #tag_id -> last write timestamp
        self._lock = threading.Lock()
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_result: Optional[Callable[[QueuedMessage, dict], None]] = None
    
    def set_result_callback(self, fn: Callable[[QueuedMessage, dict], None]) -> None:
        self._on_result = fn
        
    def enqueue(self, msg: QueuedMessage) -> None:
        """Add a message to the in-memory queue. Thread-safe"""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(lambda: self._queue.put_nowait(msg))
        else:
            self._queue.put_nowait(msg)
        log.info("[QUEUE] Enqueue command_id=%s tag_id=%s", msg.command_id, msg.tag_id)
       
    async def start(self) -> None:
        """Reload unfinished messages from gateway.db then start processing and loop."""
        from src.database import load_unfinished_messages, update_message_status
        
        self._running = True
        self._loop = asyncio.get_running_loop()
        
        # Reload any messages that didnt dfinish before last shutdown
        unfinished = load_unfinished_messages()
        for row in unfinished:
            update_message_status(row["id"], "pending")
            self._queue.put_nowait(QueuedMessage(
                command_id=row["command_id"],
                tag_id=row["tag_id"],
                payload=row["payload"],
                message_id=row["id"],
            ))
            log.info("[QUEUE] Reloaded message_id=%d tag_id=%s", row["id"], row["tag_id"])
            
        log.info("[QUEUE] Queue manager started")
        await self._process_loop()
        
    async def stop(self) -> None:
        """Graceful shutdown - unfinished messages stay as 'pending' in gateway.db."""
        from src.database import update_message_status
        
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
        from src.database import update_message_status
        
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
                
            await self._throttle_tag(msg.tag_id)
            
            # Mark as processing
            if msg.message_id is not None:
                update_message_status(msg.message_id, "processing")
            
            log.info("[QUEUE] Processing command_id=%s tag_id=%s", msg.command_id, msg.tag_id)
            
            #Pass both payload and tag_id to the write function
            result = await self._ble_write(msg.payload, msg.tag_id)
            
            log.info("[QUEUE] Result tag_id=%s ack=%s reason=%s",
                    msg.tag_id, result.get("ack"), result.get("reason"))
                    
                    
            with self._lock:
                self._last_write[msg.tag_id] = time.monotonic()
                
            # Run callback in executor to avoid blocking the event loop
            # (callback calls wait_for_publish which is blocking)
                
            if self._on_result:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    self._on_result,
                    msg,
                    result
                )
                
            self._queue.task_done()
            
    
    async def _throttle_tag(self, tag_id: int) -> None:
        with self._lock:
            last = self._last_write.get(tag_id)
        if last is not None:
            elapsed = time.monotonic() - last
            wait = self._throttle - elapsed
            if wait > 0:
                log.debug("[QUEUE] Throttling tag_id=%s for %.1fs", tag_id, wait)
                await asyncio.sleep(wait)
