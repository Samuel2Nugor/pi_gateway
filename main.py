import asyncio
import signal
import threading

from logger import get_logger
from mqtt_client import start_mqtt_client, queue_manager
#from ble_client import run_ble_scan
#from ble_client import run_ble_connect
#from ble_client import run_ble_write_test

log = get_logger("main")

def _run_mqtt(loop: asyncio.AbstractEventLoop) -> None:
    """Run paho's blocking loop in a background thread."""
    start_mqtt_client()
    
async def _main_async() -> None:
    loop = asyncio.get_running_loop()
    
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
        
    # Run queue manager until shutdown is requested
    queue_task = asyncio.create_task(queue_manager.start())
    
    await stop_event.wait()
    
    log.info("Shutting down queue manager...")
    await queue_manager.stop()
    queue_task.cancel()
    
    log.info("Gateway stopped cleanly")
    

def main() -> None:
    asyncio.run(_main_async())
    
    
  

if __name__ == "__main__":
    main()
