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

# Connection test
async def connect_to_tag() -> None:
    log.info("Connecting to BLE tag: %s", BLE.tag_address)

    async with BleakClient(BLE.tag_address) as client:
        if client.is_connected:
            log.info("Connected to Tag")
        else:
            log.warning("Failed to connect to Tag")
        log.info("Disconnected from Tag")

def run_ble_connect() -> None:
    asyncio.run(connect_to_tag())


# Wite payload + wait for ACK (notify with read fallback)
async def write_payload_to_tag_with_notify(payload: str) -> None:
    """
    Write a UTF-8 payload to the tag and return the ack response.

    Returns:
        {"ack": <str | None>, "reason": <str | None>}
    on failure:
        {"ack": "false", "reason": <reason_str>}
    """
    log.info("Connecting to Tag: %s", BLE.tag_address)

    ack_received = asyncio.Event()
    ack_value = {"text": None}

    def ack_callback(sender, data):
        ack_value["text"] = data.decode("utf-8")
        log.info("ACK notification from Tag: %s", ack_value["text"])
        ack_received.set()


    try:
        async with BleakClient(BLE.tag_address, timeout=10.0) as client:
            if not client.is_connected:
                log.warning("Failed to connect to Tag")
                return { "ack": "false", "reason": "connection_failed"}

            log.info("Connected to Tag")
            await asyncio.sleep(0.5)


            # Try to enable BLE notifications on ACK characteristic
            notify_enabled = False
            try:
                await client.start_notify(BLE.ack_char_uuid, ack_callback)
                notify_enabled = True
                log.info("ACK notification enabled")
            except Exception as error:
                log.warning("Failed to enable ACK notification: %s", error)
                log.info("Falling back to ACK read after write")

            # Write payload
            log.info("Writing payload: %s", payload)
            try:
                await client.write_gatt_char(
                    BLE.write_char_uuid,
                    payload.encode("utf-8"),
                    response=True
                )
                log.info("Payload written to Tag")
            except Exception as error:
                log.warning("BLE write failed: %s", error)
                return {"ack": "false", "reason": "write_failed"}


            # Wait for ACK
            if notify_enabled:
                log.info("Waiting for ACK notification...")

                try:
                    await asyncio.wait_for(ack_received.wait(), timeout=5.0)
                    log.info("ACK received: %s", ack_value['text'])
                except asyncio.TimeoutError:
                    log.warning("ACK notification timeout - reading ACK instead...")
                    try:
                        ack_data = await client.read_gatt_char(BLE.ack_char_uuid)
                        ack_value["text"] = ack_data.decode("utf-8")
                        log.info("ACK from Tag: %s", ack_value['text'])
                    except Exception as error:
                        log.error("ACK read failed after notify timeout: %s", error)
                        return {"ack": "false", "reason": "ack_timeout"}

                finally:
                    try:
                        await client.stop_notify(BLE.ack_char_uuid)
                        log.info("ACK notification disabled")
                    except Exception as error:
                        log.warning("Failed to stop ACK notification: %s", error)

            else:
                # Notify unavailable - direct read
                try:
                    ack_data = await client.read_gatt_char(BLE.ack_char_uuid)
                    ack_value["text"] = ack_data.decode("utf-8")
                    log.info("ACK from Tag: %s",ack_value['text'])
                except Exception as error:
                    log.error("ACK read failed:%s", error)
                    return {"ack": "false", "reason": "ack_read_failed"}

        log.info("Disconnected from Tag")
        return {"ack": ack_value["text"], "reason": None}

    except BleakError as error:
        error_text = str(error)
        log.error(f"BLE error: %s", error_text)

        if "not found" in error_text.lower():
            return {"ack": "false", "reason": "tag_not_found"}
        return {"ack": "false", "reason": "ble_error"}

    except Exception as error:
        log.error("Unexpected BLE error: %s", error)
        return {"ack": "false", "reason": "unexpected_error"}

def run_ble_write(payload: str) -> dict:
    return asyncio.run(write_payload_to_tag_with_notify(payload))

# test wrapper
def run_ble_write_test() -> None:
    test_payload = '{"tagId":"TG_01","title":"Apple 2Kg","finalPrice":"59.00 SEK"}'
    result = run_ble_write(test_payload)
    log.info(" Test result: %s", result)
