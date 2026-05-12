import paho.mqtt.client as mqtt
import json
import time

from config import MQTT
from ble_client import run_ble_write
from logger import get_logger
from database import init_db, insert_message, insert_ble_result, insert_retry
from queue_manager import QueueManager, QueuedMessage

log = get_logger("mqtt_client")

# Constants
REQUIRED_FIELDS = ["tagId", "title", "finalPrice"]

RETRY_REASONS = {
    "tag_not_found",
    "connection_failed",
    "ble_error",
    "unexpected_error"
}


# BLE retry logic
def send_to_ble_with_retries(payload: str, message_id:int, max_attempts: int = 3) -> dict:
    """
    Attempt to write payload to the BLE tag, retrying on transient errors.
    Logs each attempt to the database.
    Return the last result dict: {"ack": <str>, "reason": <str | None>}
    """

    result = {}
    
    for attempt in range(1, max_attempts + 1):
        log.info("BLE write attempt %d/%d", attempt, max_attempts)

        result = run_ble_write(payload)
        insert_retry(message_id, attempt, result["ack"], result.get("Reason"))
        
        if result["ack"] == "true":
            return result
        
        reason = result.get("reason")
        
        if reason not in RETRY_REASONS:
            log.warning("Non-retryable failure: %s", reason)
            return result

        if attempt < max_attempts:
            wait_time = attempt   # 1s, 2s backoff
            log.info("Retrying BLE write in %ds...", wait_time)
            time.sleep(wait_time)

    log.error("ALL %d BLE attempts failed. Last reason: %s", max_attempts, result.get("reason"))
    return result
 
    
# Queue result handler
_mqtt_client_ref: mqtt.Client | None = None


def _on_ble_result(msg: QueuedMessage, ble_result: dict) -> None:
    """Called by QueueManager after each BLE write completes."""
    if msg.message_id is not None:
        insert_ble_result(
            message_id=msg.message_id,
            ack=ble_result["ack"],
            reason=ble_result.get("reason"),
            attempts=ble_result.get("attempts", 1),
        )
        
    ack_payload = {
        "tagId": msg.tag_id,
        "ack": ble_result["ack"],
    }
    if ble_result.get("reason") is not None:
        ack:payload["reason"] = ble_result["reason"]
        
    if _mqtt_client_ref is None:
        log.error("MQTT client not available - cannot publish ACK")
        return
        
    log.info("Publishing ACK to %s: %s", MQTT.topic_ack, ack_payload)
    try:
        result = _mqtt_client_ref.publish(MQTT.topic_ack, json.dumps(ack_payload), qos=1)
        result.wait_for_publish(timeout =5.0)
        log.info("ACK published (rc=%d)", result.rc)
    except Exception as error:
        log.error("Failed to publish ACK: %s", error)
    

# MQTT callbacks
#Wire queue to send_to_ble_with_retries so retries + DB logging work
queue_manager = QueueManager(ble_write_fn=send_to_ble_with_retries)


def on_connect(client, userdata, flags, reason_code, properties=None) -> None:
    log.info("Connected to MQTT broker")
    client.subscribe(MQTT.topic_to_tag)

def on_message(client, userdata, message) -> None:
    global _mqtt_client_ref
    _mqtt_client_ref = client
    
    payload = message.payload.decode("utf-8")
    log.info("Received on topic %s: %s", message.topic, payload)

    # Validate JSON
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        log.warning("Invalid JSON. Message ignored.")
        return


    # Validate required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            log.warning("Missing field: %s. Message ignored.", field)
            return
            
    # Persist inbound message to database
    message_id = insert_message(
        topic=message.topic,
        tag_id=data["tagId"],
        title=data["title"],
        final_price=data["finalPrice"],
        raw_payload=payload,
    )
    
    # Enqueue for BLE write
    queue_manager.enqueue(QueuedMessage(
        tag_id=data["tagId"],
        payload=payload,
        message_id=message_id,
    ))


# Entry point
def start_mqtt_client() -> None:
    init_db()
    queue_manager.set_result_callback(_on_ble_result)
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT.broker_host, MQTT.broker_port, keepalive=60)  
    
    log.info("Starting MQTT gateway...")
    client.loop_forever()
