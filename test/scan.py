from bleak import BleakScanner
import asyncio

async def scan_ble_devices() -> None:
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5.0)

    for device in devices:
        print("Name: %s Address: %s", device.name, device.address)

def run_ble_scan() -> None:
    asyncio.run(scan_ble_devices())
    
    
if __name__ == "__main__":
    run_ble_scan()
