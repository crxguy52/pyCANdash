import can
import cantools
import time


if __name__ == "__main__":
    # def log_main(file_name: str, bus_arg: None | list[BusDescriptor], max_chunk_size: bool, suffix_format: str) -> None:
    """Log a live bus to a disk.

    Args:
        file_name: name of file to write to
        bus_arg: name of bus to read from
        max_chunk_size: max chunk size in bytes of the disk bus to rotate on
        suffix_format: suffix format of the file/rotated log file
    """

    dbPath = "./config_files/gmlan_v1.4.dbc"
    chanStr = 'virtual'

    print("Loading " + dbPath)
    db = cantools.database.load_file(dbPath)

    print("Connecting to " + chanStr)
    bus = can.Bus(interface=chanStr)

    # Create a GMLAN message
    # Start by getting a blank message
    cantoolsMsg = db.get_message_by_name('engine_general_status_1')

    # Fill in zero for all of the values
    vals = {}
    for msg in cantoolsMsg.signals:
        vals[msg.name] = 0

    pycanMsg = can.Message(\
                arbitration_id = cantoolsMsg.frame_id,\
                data = cantoolsMsg.encode(vals),
                is_extended_id=False)

    n_to_tx = 100
    n_tx = 0

    while n_to_tx > n_tx:
        bus.send(msg=msg)

        print('sent %1.0f messages' % n_tx)
        time.sleep(0.01)
        n_tx += 1

    bus.shutdown()
