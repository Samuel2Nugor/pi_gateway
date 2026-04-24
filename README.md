# Pi Gateway

Raspberry Pi Zero 2W gateway for sending MQTT payloads to an ESP32-H2 BLE tag.

The gateway receives a JSON payload from a Mosquitto MQTT topic, validates the payload, connects to the ESP32-H2 tag over BLE using Bleak, and writes the payload to the tag write characteristic.

---

## Current Status

Working:

- Mosquitto broker running on Raspberry Pi
- Python MQTT client using `paho-mqtt`
- BLE scanning using `bleak`
- BLE connection to ESP32-H2 tag
- BLE write to ESP32-H2 write characteristic
- MQTT payload forwarded to BLE tag
- E-paper display updates from received payload
- Basic JSON payload validation

---

## Hardware

- Raspberry Pi Zero 2W
- ESP32-H2 development board
- Epaper module

---

## Software

System packages on Raspberry Pi:

- mosquitto 
- mosquitto-clients 
- python3-pip 
- python3-venv

---

## Important Scope Note

This repository contains only the **Raspberry Pi gateway code**.

It does **not** contain the ESP32-H2 BLE tag firmware, and it does **not** contain any e-paper display code.

This gateway was built to connect to my own ESP32-H2 BLE tag. Because of that, the BLE device name, BLE address, service UUID, and characteristic UUIDs in `config.py` are specific to my tag.

If you use this gateway with another BLE tag, you must change those values to match your own device.

---

## Project Structure

pi_gateway/
├── main.py
├── mqtt_client.py
├── ble_client.py
├── config.py
├── requirements.txt
└── README.md

---

### Files

`main.py`

Program entry point. Starts the gateway.

`mqtt_client.py`

Connects to the Mosquitto MQTT broker, subscribes to the configured MQTT topic, receives payloads, validates the incoming JSON, and forwards valid payloads to the BLE layer.

`ble_client.py`

Handles the BLE side of the gateway. It can scan for BLE devices, connect to the configured BLE tag, and write payloads to the configured BLE write characteristic.

`config.py`

Stores configuration values used by the gateway, including:

- MQTT broker host
- MQTT broker port
- MQTT topic
- BLE tag name
- BLE tag address
- BLE service UUID
- BLE write characteristic UUID
- BLE acknowledge characteristic UUID

The BLE values are specific to my own ESP32-H2 tag and must be changed if another tag is used.

`requirements.txt`

Lists the Python packages needed by the gateway:

```txt
bleak
paho-mqtt

---

## Expected Payload

The gateway expects this JSON format:

```json
{
  "tagId": "value",     
  "title": "value",
  "finalPrice": "value"
}

---

## Setup

Install system packages on the Raspberry Pi:

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients python3-pip python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

---

## Run Gateway

start the gateway:

```bash
source .venv/bin/activate
python3 main.py


### Expected output

Connected to MQTT broker

---

## Test MQTT to BLE

In another terminal on the Raspberry Pi:

```bash
mosquitto_pub -h localhost -t esl/tag/write -m '{"tagId":"TG_01","title":"Coffee 100g","finalPrice":"49.00 SEK"}'

### Expected output

Received on topic esl/tag/write: {"tagId":"TG_01","title":"Coffee 100g","finalPrice":"49.00 SEK"}
Connecting to Tag: 74:4D:BD:63:C2:C6
Connected to Tag
Writing payload: {"tagId":"TG_01","title":"Coffee 100g","finalPrice":"49.00 SEK"}
Payload written to Tag
Disconnected from Tag

---

## NOTES

The **Tag** must be powered on, advertising, and connectable before the gateway sends BLE data.
