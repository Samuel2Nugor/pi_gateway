from dataclasses import dataclass

@dataclass(frozen=True)
class MQTTConfig:
    broker_host: str = "localhost"
    broker_port: int = 1883
    topic_to_tag: str = "esl/tag/write"
    topic_ack: str = "esl/tag/ack"
    
@dataclass(frozen=True)
class BLEConfig:
    tag_name: str = "TG_01"
    tag_id: int = 1
    tag_address: str = "74:4D:BD:63:C2:C6"
    service_uuid: str = "B8E4F533-E530-4D1D-B54C-0D5D5A9A5A4B"
    write_char_uuid: str = "99CFD161-DCD8-4BEB-86B2-48673AEAE284"
    ack_char_uuid: str = "53B04C05-A5E1-475B-BC9E-61C00112ACDE"
    
    
# Singleton instances - import these directly
MQTT = MQTTConfig()
BLE = BLEConfig()


# Flat aliases for backwards compatibility
MQTT_BROKER_HOST = MQTT.broker_host
MQTT_BROKER_PORT = MQTT.broker_port
MQTT_TOPIC_TO_TAG = MQTT.topic_to_tag
MQTT_TOPIC_ACK = MQTT.topic_ack

BLE_TAG_NAME = BLE.tag_name
BLE_TAG_ID = BLE.tag_id
BLE_TAG_ADDRESS = BLE.tag_address
SERVICE_UUID = BLE.service_uuid
WRITE_CHAR_UUID = BLE.write_char_uuid
ACK_CHAR_UUID = BLE.ack_char_uuid
