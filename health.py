import asyncio
import sqlite3
import paho.mqtt.client as mqtt

from config import MQTT, BLE
from logger import get_logger

log = get_logger("health")

def check_mqtt() -> dict:
    """check if the MQTT broker is reachable."""
    result = {"status": "ok", "host": MQTT.broker_host, "port": MQTT.broker_port}
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(MQTT.broker_host, MQTT.broker_port, keepalive=5)
        client.disconnect()
    except Exception as error:
        result["status"] = "error"
        result["error"] = str(error)
    return result
    
def check_database() -> dict:
    """Check if gateway.db is accesible and tables exixt."""
    result = {"status": "ok", "path": "gateway.db"}
    try:
        conn = sqlite3.connect("gateway.db")
        tables = conn.execute(
            "Select name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        result["tables"] = [t[0] for t in tables]
    except Exception as error:
        result["status"] = "error"
        result["error"] = str(error)
    return result
    
async def check_ble() -> dict:
    """Check if the BLE tag is discoverable."""
    from bleak import BleakScanner
    result = {"status": "ok", "tag_address": BLE.tag_address}
    try:
        device = await BleakScanner.find_device_by_address(BLE.tag_address, timeout=5.0)
        if device is None:
            result["status"] = "unreachable"
            result["note"] = "Tag not found within timeout"
        else:
            result["name"] = device.name
    except Exception as error:
        result["status"] = "error"
        result["error"] = str(error)
    return result
    
async def run_health_check() -> dict:
    log.info("Running healt check...")
    
    mqtt_result = check_mqtt()
    db_result = check_database()
    ble_result = await check_ble()
    
    report = {
        "mqtt":     mqtt_result,
        "database": db_result,
        "ble":      ble_result,
        "overall":  "ok"
    }
    
    # Overall is degrades only on hard errors
    if any(r["status"] == "error" for r in [mqtt_result, db_result, ble_result]):
        report["overall"] = "degraded"
        
    log.info("Health check result: overall=%s", report["overall"])
    log.info("  MQTT:       %s", mqtt_result)
    log.info("  Database:   %s", db_result)
    log.info("  BLE:        %s", ble_result)
    
    return report
    
    
def run_health() -> dict:
    return asyncio.run(run_health_check())
    

if __name__ == "__main__":
    import json
    report = run_health()
    print(json.dumps(report, indent=2))
    
    
            
