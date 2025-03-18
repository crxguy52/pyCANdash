import can
import cantools
import logging
import time

def list_available_interfaces():
    """Lists available CAN interfaces."""
    available_interfaces = can.interface.detect_available_configs()
    if available_interfaces:
        print("Available CAN interfaces:")
        for interface in available_interfaces:
            print(f"- {interface}")
    else:
        print("No CAN interfaces found.")

def configLogger():
    # Configure the logger
    logFormatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%d-%b-%Y %H:%M:%S")
    # Log to the console
    stderr_log_handler = logging.StreamHandler()
    stderr_log_handler.setFormatter(logFormatter) 
    logging.getLogger().addHandler(stderr_log_handler) 
    logging.getLogger().setLevel("INFO")  

if __name__ == '__main__':
    #list_available_interfaces()
    configLogger()       
    t_log_s = 0.025

    logging.info('Loading DBC')
    dbcPath = 'C:/git/pyrofuse-bit-prototype/tmp/pyrofuse-bit-prototype.dbc'
    db = cantools.database.load_file(dbcPath)

    logging.info('Opening bus')
    bus = can.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500e3)

    t_end = time.time() + t_log_s

    while time.time() < t_end:
        msg = bus.recv(timeout=0)       

        try:
            if msg is not None:

                # Decode it
                decodedDict = db.decode_message(msg.arbitration_id, msg.data)

                # Iterate over all of the signals
                for key in decodedDict:
                    print(f"{str(key):>25}: {str(decodedDict[key])}") 
        except Exception as e:
            #logging.exception(e)
            #print(str(type(e)) + ':' + str(e))
            pass
                
    
    logging.info('Shutting down bus')
    bus.shutdown()

    logging.info('Done')
