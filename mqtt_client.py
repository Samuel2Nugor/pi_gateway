import paho.mqtt.client as mqtt
import json

from config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_TO_TAG
from ble_client import run_ble_write


def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Connected to MQTT broker")
    client.subscribe(MQTT_TOPIC_TO_TAG)


def on_message(client, userdata, message):
    payload = message.payload.decode("utf-8")
    print(f"Recieved on topic {message.topic}: {payload}")

    run_ble_write(payload)


def start_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)       # host, port
    client.loop_forever()
