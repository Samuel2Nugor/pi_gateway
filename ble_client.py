import asyncio
from bleak import BleakClient, BleakScanner, BleakError
from config import BLE_TAG_ADDRESS, WRITE_CHAR_UUID, ACK_CHAR_UUID

# Scanning

async def scan_ble_devices() -> None:
    print("Scanning for BLE devices...")

    devices = await BleakScanner.discover(timeout=5.0)

    for device in devices:
        print(f"Name: {device.name}, Address: {device.address}")

def run_ble_scan() -> None:
    asyncio.run(scan_ble_devices())

# Connection test
async def connect_to_tag() -> None:
    print(f"Connecting to BLE tag: {BLE_TAG_ADDRESS}")

    async with BleakClient(BLE_TAG_ADDRESS) as client:
        if client.is_connected:
            print("Connected to Tag")
        else:
            print("Failed to connect to Tag")

        print("Disconnected from Tag")

def run_ble_connect() -> None:
    asyncio.run(connect_to_tag())


async def write_payload_to_tag(payload: str) -> dict:   # BLE Write + ACK Read
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


# Wite payload + wait for ACK (notify with read fallback)
async def write_payload_to_tag_with_notify(payload: str) -> None:
    """
    Write a UTF-8 payload to the tag and return the ack response.

    Returns:
        {"ack": <str | None>, "reason": <str | None>}
    on failure:
        {"ack": "false", "reason": <reason_str>}
    """
    print(f"[BLE] Connecting to Tag: {BLE_TAG_ADDRESS}")

    ack_received = asyncio.Event()
    ack_value = {"text": None}

    def ack_callback(sender, data):
        ack_value["text"] = data.decode("utf-8")
        print(f"[BLE] ACK notification from Tag: {ack_value['text']}")
        ack_received.set()


    try:
        async with BleakClient(BLE_TAG_ADDRESS, timeout=10.0) as client:
            if not client.is_connected:
                print("[BLE] Failed to connect to Tag")
                return { "ack": "false", "reason": "connection_failed"}

            print("[BLE] Connected to Tag")
            await asyncio.sleep(0.5)


            # Try to enable BLE notifications on ACK characteristic
            notify_enabled = False

            try:
                await client.start_notify(ACK_CHAR_UUID, ack_callback)
                notify_enabled = True
                print("[BLE] ACK notification enabled")
            except Exception as error:
                print(f"[BLE] Failed to enable ACK notification: {error}")
                print("[BLE] Falling back to ACK read after write")

            # Write payload
            print(f"[BLE] Writing payload: {payload}")
            try:
                await client.write_gatt_char(
                    WRITE_CHAR_UUID,
                    payload.encode("utf-8"),
                    response=True
                )
                print("Payload written to Tag")
            except Exception as error:
                print(f"BLE write failed: {error}")
                return {"ack": "false", "reason": "write_failed"}


            # Wait for ACK
            if notify_enabled:
                print("[BLE] Waiting for ACK notification...")

                try:
                    await asyncio.wait_for(ack_received.wait(), timeout=5.0)
                    print(f"ACK received: {ack_value['text']}")

                except asyncio.TimeoutError:
                    print("ACK notification timeout - reading ACK instead...")

                    try:
                        ack_data = await client.read_gatt_char(ACK_CHAR_UUID)
                        ack_value["text"] = ack_data.decode("utf-8")
                        print(f"[BLE] ACK from Tag: {ack_value['text']}")
                    except Exception as error:
                        print(f"[BLE] ACK read failed after notify timeout: {error}")
                        return {"ack": "false", "reason": "ack_timeout"}

                finally:
                    try:
                        await client.stop_notify(ACK_CHAR_UUID)
                        print("[BLE] ACK notification disabled")
                    except Exception as error:
                        print(f"Failed to stop ACK notification: {error}")

            else:
                # Notify unavailable - direct read
                try:
                    ack_data = await client.read_gatt_char(ACK_CHAR_UUID)
                    ack_value["text"] = ack_data.decode("utf-8")
                    print(f"[BLE] ACK from Tag: {ack_value['text']}")
                except Exception as error:
                    print(f"ACK read failed: {error}")
                    return {"ack": "false", "reason": "ack_read_failed"}

        print("Disconnected from Tag")
        return {"ack": ack_value["text"], "reason": None}

    except BleakError as error:
        error_text = str(error)
        print(f"BLE error: {error_text}")

        if "not found" in error_text.lower():
            return {"ack": "false", "reason": "tag_not_found"}

        return {"ack": "false", "reason": "ble_error"}

    except Exception as error:
        print(f"Unexpected BLE error: {error}")
        return {"ack": "false", "reason": "unexpected_error"}

def run_ble_write(payload: str) -> dict:
    return asyncio.run(write_payload_to_tag_with_notify(payload))

# test wrapper
def run_ble_write_test() -> None:
    test_payload = '{"tagId":"TG_01","title":"Apple 2Kg","finalPrice":"59.00 SEK"}'
    result = run_ble_write(test_payload)
    print(f"[TEST] Result: {result}")
