# main.py
#from mqtt_client import start_mqtt_client
from ble_client import run_ble_scan

def main():
    #start_mqtt_client()
    run_ble_scan()


if __name__ == "__main__":
    main()