from dataclasses import dataclass

@dataclass(frozen=True)
class MQTTConfig:
    broker_host: str = "localhost"
    broker_port: int = 1883
    topic_to_tag: str = "esl/tag/write"
    topic_ack: str = "esl/tag/ack"
    


@dataclass(frozen=True)
class BLEProtocolConfig:
    service_uuid: str = "FA6AB636-39CE-448F-9EB1-C052BCCEA345"
    write_char_uuid: str = "17D753B6-F433-4825-8D6E-76412A446C3B"
    ack_char_uuid: str = "6085C081-65BD-4C76-8656-D94622184641"
    
    
@dataclass(frozen=True)
class TagInfo:
    name: str
    address: str
    
    
TAGS = {
    1: TagInfo(
        
        name="TG_01",
        address="74:4D:BD:63:C2:C6",
    ),
    2: TagInfo(
        name="TG_02",
        address="44:1B:F6:D4:00:B9",
    ),
    3: TagInfo(
        name="TG_03",
        address="44:1B:F6:D3:6B:D1",
    )
}
        
        

    
    
# Singleton instances - import these directly
MQTT = MQTTConfig()
BLE_PROTOCOL = BLEProtocolConfig()



