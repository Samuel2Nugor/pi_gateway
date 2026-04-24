# main.py
from mqtt_client import start_mqtt_client
#from ble_client import run_ble_scan
#from ble_client import run_ble_connect
#from ble_client import run_ble_write_test

def main():
    start_mqtt_client()
    #run_ble_scan()
    #run_ble_connect()
    #run_ble_write_test()

if __name__ == "__main__":
    main()