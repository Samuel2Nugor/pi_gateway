from src.config import MQTT, BLE


def test_gateway_mqtt_topics_are_configured():
    assert MQTT.topic_to_tag == "esl/tag/write"
    assert MQTT.topic_ack == "esl/tag/ack"
    
    
def test_ble_config_has_required_values():
    assert BLE.tag_id == 1
    assert BLE.write_char_uuid
    assert BLE.ack_char_uuid
