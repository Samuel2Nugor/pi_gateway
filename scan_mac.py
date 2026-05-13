import asyncio
from bleak import BleakClient, BleakScanner, BleakError

from config import BLE
from logger import get_logger

log = get_logger("ble-client")

# Scanning

async def scan_ble_devices() -> None:
    log.info("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5.0)

    for device in devices:
        log.info("Name: %s Address: %s", device.name, device.address)

def run_ble_scan() -> None:
    asyncio.run(scan_ble_devices())



run_ble_scan();
