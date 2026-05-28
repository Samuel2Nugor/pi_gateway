import asyncio

from bleak import BleakClient, BleakScanner, BleakError

from src.config import BLE_PROTOCOL, TAGS
from src.logger import get_logger

log = get_logger("ble-client")


def _get_tag_config(tag_id: int):
    tag = TAGS.get(tag_id)
    if tag is None:
        log.warning("Unknown tag_id=%s", tag_id)
        return None
    return tag


async def scan_ble_devices() -> None:
    log.info("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    for device in devices:
        log.info("Name: %s Address: %s", device.name, device.address)


def run_ble_scan() -> None:
    asyncio.run(scan_ble_devices())


async def write_payload_to_tag(payload: str, tag_id: int) -> dict:
    """
    Write a UTF-8 payload to the selected BLE tag and wait for ACK.
    Returns:
        {"ack": "true", "reason": None}
        {"ack": "false", "reason": "<reason>"}
    """
    log.info("write_payload_to_tag called tag_id=%s", tag_id)
    tag = _get_tag_config(tag_id)
    if tag is None:
        return {"ack": "false", "reason": "tag_not_found"}
        
    log.info("Got tag config for tag_id=%s", tag_id)


    log.info("Connecting to tag_id=%s name=%s address=%s", tag_id, tag.name, tag.address)

    ack_received = asyncio.Event()
    ack_value = {"text": None}

    def ack_callback(sender, data):
        ack_value["text"] = data.decode("utf-8")
        log.info("ACK from tag_id=%s: %s", tag_id, ack_value["text"])
        ack_received.set()

    try:
        async with BleakClient(tag.address, timeout=10.0) as client:
            if not client.is_connected:
                log.warning("Failed to connect to tag_id=%s", tag_id)
                return {"ack": "false", "reason": "connection_failed"}

            await asyncio.sleep(0.5)

            notify_enabled = False
            try:
                await client.start_notify(BLE_PROTOCOL.ack_char_uuid, ack_callback)
                notify_enabled = True
            except Exception as error:
                log.warning("ACK notify unavailable: %s", error)

            try:
                await client.write_gatt_char(
                    BLE_PROTOCOL.write_char_uuid,
                    payload.encode("utf-8"),
                    response=True,
                )
                log.info("Payload written to tag_id=%s", tag_id)
            except Exception as error:
                log.warning("BLE write failed: %s", error)
                return {"ack": "false", "reason": "ble_error"}

            if notify_enabled:
                try:
                    await asyncio.wait_for(ack_received.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    log.warning("ACK notify timeout, reading directly...")
                    try:
                        ack_data = await client.read_gatt_char(BLE_PROTOCOL.ack_char_uuid)
                        ack_value["text"] = ack_data.decode("utf-8")
                    except Exception as error:
                        log.error("ACK read failed: %s", error)
                        return {"ack": "false", "reason": "ack_timeout"}
                finally:
                    try:
                        await client.stop_notify(BLE_PROTOCOL.ack_char_uuid)
                    except Exception as error:
                        log.warning("Failed to stop notify: %s", error)
            else:
                try:
                    ack_data = await client.read_gatt_char(BLE_PROTOCOL.ack_char_uuid)
                    ack_value["text"] = ack_data.decode("utf-8")
                    log.info("ACK read from tag_id=%s: %s", tag_id, ack_value["text"])
                except Exception as error:
                    log.error("ACK read failed: %s", error)
                    return {"ack": "false", "reason": "ack_read_failed"}

        return {"ack": ack_value["text"], "reason": None}

    except BleakError as error:
        error_text = str(error)
        log.error("BLE error: %s", error_text)
        if "not found" in error_text.lower():
            return {"ack": "false", "reason": "tag_not_found"}
        return {"ack": "false", "reason": "ble_error"}

    except Exception as error:
        log.error("Unexpected BLE error: %s", error)
        return {"ack": "false", "reason": "unexpected_error"}
