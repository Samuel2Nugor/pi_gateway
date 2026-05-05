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
- Basic JSON payload validation

---

## Hardware

- Raspberry Pi Zero 2W

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
