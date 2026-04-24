# ble_client
import asyncio
from bleak import BleakScanner



async def scan_ble_devices():
    print("Scanning for BLE devices...")

    devices = await BleakScanner.discover(timeout=5.0)

    for device in devices:
        print(f"Name: {device.name}, Address: {device.address}")

def run_ble_scan():
    asyncio.run(scan_ble_devices())