import paho.mqtt.client as mqtt
import json
import time

from config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_TO_TAG, MQTT_TOPIC_ACK
from ble_client import run_ble_write


def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Connected to MQTT broker")
    client.subscribe(MQTT_TOPIC_TO_TAG)

def send_to_ble_with_retries(payload: str, max_attempts: int = 3):
    retry_reasons = {
        "tag_not_found",
        "connection_failed",
        "ble_error",
        "unexpected_error"
    }

    for attempt in range(1, max_attempts + 1):
        print(f"BLE write attempt {attempt}/{max_attempts}")

        result = run_ble_write(payload)

        if result["ack"] == "true":
            return result

        reason = result.get("reason")

        if reason not in retry_reasons:
            return result
        
        if attempt < max_attempts:
            wait_time = attempt
            print(f"Retrying BLE write in {wait_time} second(s)...")
            time.sleep(wait_time)

    return result


def on_message(client, userdata, message):
    payload = message.payload.decode("utf-8")
    print(f"Recieved on topic {message.topic}: {payload}")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print("Invalid JSON. Message ignored.")
        return

    requires_fields = ["tagId", "title", "finalPrice"]

    for field in requires_fields:
        if field not in data:
            print(f"Missing field: {field}. Message ignored")
            return

    ble_result = send_to_ble_with_retries(payload)

    ack_payload = {
        "tagId": data["tagId"],
        "ack": ble_result["ack"]
    }

    if ble_result["reason"] is not None:
        ack_payload["reason"] = ble_result["reason"]

    client.publish(MQTT_TOPIC_ACK, json.dumps(ack_payload))
    print(f"Published ACK to {MQTT_TOPIC_ACK}: {ack_payload}")


def start_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)       # host, port
    client.loop_forever()
