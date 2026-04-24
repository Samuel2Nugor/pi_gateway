import asyncio
from bleak import BleakClient, BleakScanner

from config import BLE_TAG_ADDRESS


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