from src.config import MQTT, BLE_PROTOCOL, TAGS


def test_gateway_mqtt_topics_are_configured():
    assert MQTT.topic_to_tag == "esl/tag/write"
    assert MQTT.topic_ack == "esl/tag/ack"
    
    
    
def test_ble_protocol_has_required_values():
    assert BLE_PROTOCOL.service_uuid
    assert BLE_PROTOCOL.write_char_uuid
    assert BLE_PROTOCOL.ack_char_uuid
    
    
def test_gateway_has_registered_tags():
    assert 1 in TAGS
    assert TAGS[1].tag_name == "TG_01"
    assert TAGS[1].tag_address 
