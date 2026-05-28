import asyncio
import json

import paho.mqtt.client as mqtt

from src.config import MQTT
from src.ble_client import write_payload_to_tag
from src.logger import get_logger
from src.database import insert_message, update_message_status
from src.queue_manager import QueueManager, QueuedMessage

log = get_logger("mqtt_client")

REQUIRED_FIELDS = ["commandId", "tagId", "title", "finalPrice"]

RETRY_REASONS = {
    "tag_not_found",
    "connection_failed",
    "ble_error",
    "unexpected_error",
}

_mqtt_client_ref: mqtt.Client | None = None


async def send_to_ble_with_retries(payload: str, tag_id: int, max_attempts: int = 3) -> dict:
    """Attempt BLE write with retries."""
    result = {
        "ack": "false",
        "reason": "unexpected_error",
        "attempts": 0,
    }

    for attempt in range(1, max_attempts + 1):
        log.info("BLE attempt %d/%d for tag_id=%s", attempt, max_attempts, tag_id)
        result = await write_payload_to_tag(payload, tag_id)
        result["attempt"] = attempt

        if result["ack"] == "true":
            return result

        reason = result.get("reason")
        if reason not in RETRY_REASONS:
            log.warning("Non-retryable failure: %s", reason)
            return result

        if attempt < max_attempts:
            wait_time = attempt
            log.info("Retrying BLE in %ds...", wait_time)
            await asyncio.sleep(wait_time)

    log.error("All %d BLE attempts failed.", max_attempts)
    return result


def _publish_ack(msg: QueuedMessage, ble_result: dict) -> None:
    """Called by QueueManager after each BLE write completes."""
    ack_payload = {
        "commandId": msg.command_id,
        "tagId": msg.tag_id,
        "ack": ble_result["ack"],
    }

    if ble_result.get("reason") is not None:
        ack_payload["reason"] = ble_result["reason"]

    if _mqtt_client_ref is None:
        log.error("MQTT client not available - cannot publish ACK")
        return

    try:
        result = _mqtt_client_ref.publish(MQTT.topic_ack, json.dumps(ack_payload), qos=1)
        result.wait_for_publish(timeout=5.0)
        log.info("ACK published rc=%d", result.rc)
    except Exception as error:
        log.error("Failed to publish ACK: %s", error)


def _on_ble_result(msg: QueuedMessage, ble_result: dict) -> None:
    """Called by QueueManager after BLE write completes."""
    if msg.message_id is not None:
        if ble_result["ack"] == "true":
            update_message_status(msg.message_id, "acked")
        else:
            update_message_status(msg.message_id, "failed")

    _publish_ack(msg, ble_result)


queue_manager = QueueManager(ble_write_fn=send_to_ble_with_retries)


def _validate_message(data: dict) -> bool:
    for field in REQUIRED_FIELDS:
        if field not in data:
            log.warning("Missing field: %s. Message ignored.", field)
            return False
    return True


def on_connect(client, userdata, flags, reason_code, properties=None) -> None:
    log.info("Connected to MQTT broker")
    client.subscribe(MQTT.topic_to_tag)


def on_message(client, userdata, message) -> None:
    global _mqtt_client_ref
    _mqtt_client_ref = client

    payload = message.payload.decode("utf-8")
    log.info("Received on topic %s: %s", message.topic, payload)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        log.warning("Invalid JSON. Message ignored.")
        return

    if not _validate_message(data):
        return

    try:
        message_id = insert_message(
            command_id=data["commandId"],
            topic=message.topic,
            tag_id=data["tagId"],
            title=data["title"],
            final_price=data["finalPrice"],
            raw_payload=payload,
        )
    except Exception as error:
        log.error("Failed to insert message: %s", error)
        return

    

    queue_manager.enqueue(QueuedMessage(
        command_id=data["commandId"],
        tag_id=data["tagId"],
        payload=payload,
        message_id=message_id,
    ))


def start_mqtt_client() -> None:
    queue_manager.set_result_callback(_on_ble_result)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    global _mqtt_client_ref
    _mqtt_client_ref = client

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT.broker_host, MQTT.broker_port, keepalive=60)
    log.info("Starting MQTT gateway...")
    client.loop_forever()
