import asyncio
from bleak import BleakClient, BleakScanner, BleakError

from config import BLE_TAG_ADDRESS, WRITE_CHAR_UUID, ACK_CHAR_UUID


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

async def write_payload_to_tag(payload: str):   # BLE Write + ACK Read
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

        ack_data = await client.read_gatt_char(ACK_CHAR_UUID)
        ack_text = ack_data.decode("utf-8")

        print(f"ACK from Tag: {ack_text}")
    
    print("Disconnected from Tag")

async def write_payload_to_tag_with_notify(payload: str):
    ack_received = asyncio.Event()
    ack_value = {"text": None}

    def ack_callback(sender, data):
        ack_text = data.decode("utf-8")
        ack_value["text"] = ack_text
        print(f"ACK notification from Tag: {ack_text}")
        ack_received.set()

    print(f"Connecting to Tag: {BLE_TAG_ADDRESS}")

    try:
        async with BleakClient(BLE_TAG_ADDRESS) as client:
            if not client.is_connected:
                print("Failed to connect to Tag")
                return {
                    "ack": "false",
                    "reason": "connection_failed"
                }

            print("Connected to Tag")

            await asyncio.sleep(0.5)

            notify_enabled = False

            try:
                await client.start_notify(ACK_CHAR_UUID, ack_callback)
                notify_enabled = True
                print("ACK notification enabled")
            except Exception as error:
                print(f"Failed to enable ACK notification: {error}")
                print("Falling back to ACK read after write")
                notify_enabled = False

            print(f"Writing payload: {payload}")

            try:
                await client.write_gatt_char(
                    WRITE_CHAR_UUID,
                    payload.encode("utf-8"),
                    response=True
                )
                print("Payload written to Tag")
            except Exception as error:
                print(f"BLE write failed: {error}")
                return {
                    "ack": "false",
                    "reason": "write_failed"
                }

            if notify_enabled:
                print("Waiting for ACK notification...")

                try:
                    await asyncio.wait_for(ack_received.wait(), timeout=5.0)
                    print(f"ACK received: {ack_value['text']}")

                except asyncio.TimeoutError:
                    print("ACK notification timeout")
                    print("Reading ACK instead...")

                    try:
                        ack_data = await client.read_gatt_char(ACK_CHAR_UUID)
                        ack_value["text"] = ack_data.decode("utf-8")
                        print(f"ACK from Tag: {ack_value['text']}")
                    except Exception as error:
                        print(f"ACK read failed after notify timeout: {error}")
                        return {
                            "ack": "false",
                            "reason": "ack_timeout"
                        }

                try:
                    await client.stop_notify(ACK_CHAR_UUID)
                    print("ACK notification disabled")
                except Exception as error:
                    print(f"Failed to stop ACK notification: {error}")

            else:
                try:
                    ack_data = await client.read_gatt_char(ACK_CHAR_UUID)
                    ack_value["text"] = ack_data.decode("utf-8")
                    print(f"ACK from Tag: {ack_value['text']}")
                except Exception as error:
                    print(f"ACK read failed: {error}")
                    return {
                        "ack": "false",
                        "reason": "ack_read_failed"
                    }

        print("Disconnected from Tag")

        return {
            "ack": ack_value["text"],
            "reason": None
        }

    except BleakError as error:
        error_text = str(error)
        print(f"BLE error: {error_text}")

        if "not found" in error_text.lower():
            return {
                "ack": "false",
                "reason": "tag_not_found"
            }

        return {
            "ack": "false",
            "reason": "ble_error"
        }

    except Exception as error:
        print(f"Unexpected BLE error: {error}")
        return {
            "ack": "false",
            "reason": "unexpected_error"
        }
    
def run_ble_write(payload: str):
    return asyncio.run(write_payload_to_tag_with_notify(payload))

# test wrapper
def run_ble_write_test():
    test_payload = '{"tagId":"TG_01","title":"Apple 2Kg","finalPrice":"59.00 SEK"}'
    run_ble_write(test_payload)