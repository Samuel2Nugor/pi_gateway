import asyncio
from bleak import BleakClient, BleakScanner

from config import BLE_TAG_ADDRESS, WRITE_CHAR_UUID


async def scan_ble_devices():
    print("Scanning for BLE devices...")

    devices = await BleakScanner.discover(timeout=5.0)

    for device in devices:
        print(f"Name: {device.name}, Address: {device.address}")

def run_ble_scan():
    asyncio.run(scan_ble_devices())

async def connect_to_tag():
    print(f"Connecting to BLE tag: {BLE_TAG_ADDRESS}")

    async with BleakClient(BLE_TAG_ADDRESS) as client:
        if client.is_connected:
            print("Connected to Tag")
        else:
            print("Failed to connect to Tag")

        print("Disconnected from Tag")

def run_ble_connect():
    asyncio.run(connect_to_tag())

async def write_payload_to_tag(payload: str):
    print(f"Connecting to Tag: {BLE_TAG_ADDRESS}")

    async with BleakClient(BLE_TAG_ADDRESS) as client:
        if not client.is_connected:
            print("Failed to connect to Tag")
            return

        print("Connected to Tag")
        print(f"Writing payload: {payload}")

        await client.write_gatt_char(
            WRITE_CHAR_UUID,
            payload.encode("utf-8"),
            response=True
        )

        print("Payload wriiten to Tag")
    
    print("Disconnected from Tag")

def run_ble_write(payload: str):
    asyncio.run(write_payload_to_tag(payload))

# test wrapper
def run_ble_write_test():
    test_payload = '{"tagId":"TG_01","title":"Apple 2Kg","finalPrice":"59.00 SEK"}'
    run_ble_write(test_payload)