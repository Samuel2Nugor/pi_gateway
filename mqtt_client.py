import paho.mqtt.client as mqtt


def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Connected to MQTT broker")
    client.subscribe("esl/tag/write")


def on_message(client, userdata, message):
    payload = message.payload.decode("utf-8")
    print(f"Recieved on topic {message.topic}: {payload}")


def start_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("localhost", 1883, 60)       # host, port
    client.loop_foreever()