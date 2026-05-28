import asyncio
import signal
import threading

from src.database import init_db
from src.logger import get_logger
from src.mqtt_client import start_mqtt_client, queue_manager


log = get_logger("main")

def _run_mqtt(loop: asyncio.AbstractEventLoop) -> None:
    """Run paho's blocking loop in a background thread."""
    start_mqtt_client()
    
async def _main_async() -> None:
    loop = asyncio.get_running_loop()
    
    init_db()
    
    # Start queue_manager FIRST so it's ready before MQTT receives anything
    queue_task = asyncio.create_task(queue_manager.start())
    
    # Small yield to let queue-manager.start() run and self._loop
    await asyncio.sleep(0.1)
    
    # Start paho MQTT in a background thread so it doesn't block the event loop
    mqtt_thread = threading.Thread(target=_run_mqtt, args=(loop,), daemon=True, name="mqtt")
    mqtt_thread.start()
    log.info("MQTT thread started")
    
    # Graceful shutdown on SIGINT / SIGTERM
    stop_event = asyncio.Event()
    
    def _signal_handler():
        log.info("Shutdown signal received")
        stop_event.set()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)
        
    
    await stop_event.wait()
    
    log.info("Shutting down...")
    await queue_manager.stop()
    queue_task.cancel()
    
    log.info("Gateway stopped cleanly")
    

def main() -> None:
    asyncio.run(_main_async())
    
    
  

if __name__ == "__main__":
    main()
