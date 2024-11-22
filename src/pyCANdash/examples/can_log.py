from beta.can.buses import DiskBus, DiskBusMode
from beta.can_utils.decode import main as decode
import can
import time
import logging


if __name__ == "__main__":
    # def log_main(file_name: str, bus_arg: None | list[BusDescriptor], max_chunk_size: bool, suffix_format: str) -> None:
    """Log a live bus to a disk.

    Args:
        file_name: name of file to write to
        bus_arg: name of bus to read from
        max_chunk_size: max chunk size in bytes of the disk bus to rotate on
        suffix_format: suffix format of the file/rotated log file
    """

    file_name = "./data/test.dat"
    dbpath = "./beta/hvir_control/examples/test.dbc"
    # max_chunk_size = 128

    # logging.getLogger("can.gateway").setLevel("DEBUG")
    # logging.getLogger("can.gateway").addHandler(logging.StreamHandler())

    # bus_arg: list[BusDescriptor] = 'busname'
    # bus_to_use = bus_arg or [BusDescriptor("udp", "multicast")]

    # bus: BetaBusABC = _get_bus(bus_to_use, receiving=True)
    # bus: BetaBusABC = bus_arg[0].create_bus(receiving=True)
    local_ip = "192.168.1.1"
    local_port = "55002"
    remote_ip = "192.168.1.10"
    remote_port = "55002"
    chanstr = f"{local_ip}:{local_port},{remote_ip}:{remote_port}"
    print("Connecting to " + chanstr)
    bus = can.Bus(bustype="gateway", channel=chanstr)

    with DiskBus(file_name, mode=DiskBusMode.LOG) as disk_bus:
        # Record the bus while some condition is met

        for i in range(0, 1000):
            msg = can.Message(
                arbitration_id=0x100,
                data=[0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68],
                is_extended_id=True,
                is_fd=True,
                bitrate_switch=True,
                check=True,
            )
            bus.send(msg=msg)
            time.sleep(0.01)
            data = bus.recv()

            print(data)
            disk_bus.send(data)

# When we're done logging, Decode the bus
print("Decoding data in wide format")
decode(
    source_file_name=file_name,
    output_target=file_name[:-4] + "_wide.csv",
    dbc_file=dbpath,
    disable_time_machine=True,
    timestamp="sent",
)

print("Decoding data in tall format (better time resolution)")
decode(
    source_file_name=file_name,
    output_target=file_name[:-4] + "_tall.csv",
    dbc_file=dbpath,
    disable_time_machine=True,
    timestamp="sent",
    decode_format="tall",
)

print("--> done <--")
bus.shutdown()
