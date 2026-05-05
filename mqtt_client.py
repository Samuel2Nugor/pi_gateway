import paho.mqtt.client as mqtt
import json
import time

from config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_TO_TAG, MQTT_TOPIC_ACK
from ble_client import run_ble_write

# Constants

REQUIRED_FIELDS = ["tagId", "title", "finalPrice"]

RETRY_REASONS = {
    "tag_not_found",
    "connection_failed",
    "ble_error",
    "unexpected_error"
}


# BLE retry logic

def send_to_ble_with_retries(payload: str, max_attempts: int = 3) -> dict:
    """
    Attempt to write payload to the BLE tag, retrying on transient errors.

    Return the last result dict: {"ack": <str>, "reason": <str | None>}
    """

    result = {}

    for attempt in range(1, max_attempts + 1):
        print(f"[MQTT] BLE write attempt {attempt}/{max_attempts}")

        result = run_ble_write(payload)

        if result["ack"] == "true":
            return result

        reason = result.get("reason")

        if reason not in RETRY_REASONS:
            return result

        if attempt < max_attempts:
            wait_time = attempt   # 1s, 2s backoff
            print(f"[MQTT] Retrying BLE write in {wait_time} second(s)...")
            time.sleep(wait_time)

    return result

# MQTT callbacks

def on_connect(client, userdate, flags, reason_code, properties=None) -> None:
    print("[MQTT] Connected to MQTT broker")
    client.subscribe(MQTT_TOPIC_TO_TAG)

def on_message(client, userdata, message) -> None:
    payload = message.payload.decode("utf-8")
    print(f"[MQTT] Recieved on topic {message.topic}: {payload}")

    # Validate JSON
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print("[MQTT] Invalid JSON. Message ignored.")
        return


    # Validate required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            print(f"[MQTT] Missing field: {field}. Message ignored")
            return

    # Foward to TAG
    ble_result = send_to_ble_with_retries(payload)

    # Build ACK payload
    ack_payload = {
        "tagId": data["tagId"],
        "ack": ble_result["ack"]
    }

    if ble_result["reason"] is not None:
        ack_payload["reason"] = ble_result["reason"]

    # Publish ACK back to broker
    print(f"[MQTT] Publishing ACK to {MQTT_TOPIC_ACK}: {ack_payload}")
    try:
        result = client.publish(MQTT_TOPIC_ACK, json.dumps(ack_payload), qos=1)
        result.wait_for_publish(timeout=5.0)
        print(f"[MQTT] ACK published (rc={result.rc}")
    except Exception as error:
        print(f"[MQTT] Failed to publish ACK: {error}")

# Entry point
def start_mqtt_client() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)       # host, port
    client.loop_forever()
