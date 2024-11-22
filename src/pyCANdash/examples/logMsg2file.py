import can

CANFD_BRS = 0x01
CANFD_ESI = 0x02

msg = can.Message(
    arbitration_id=0x100,
    data=[0x61],
    is_extended_id=True,
    is_fd=True,
    bitrate_switch=True,
    check=True,
)


last_timestamp = None
channel = 'vcan0'

logger = can.Logger('C:/Users/VictorZaccardo/Desktop/test.log')

# this is the case for the very first message:
if last_timestamp is None:
    last_timestamp = msg.timestamp or 0.0

# figure out the correct timestamp
if msg.timestamp is None or msg.timestamp < last_timestamp:
    timestamp = self.last_timestamp
else:
    timestamp = msg.timestamp

channel = msg.channel if msg.channel is not None else channel
if isinstance(channel, int) or isinstance(channel, str) and channel.isdigit():
    channel = f"can{channel}"

framestr = f"({timestamp:f}) {channel}"

if msg.is_error_frame:
    framestr += f" {CAN_ERR_FLAG | CAN_ERR_BUSERROR:08X}#"
elif msg.is_extended_id:
    framestr += f" {msg.arbitration_id:08X}#"
else:
    framestr += f" {msg.arbitration_id:03X}#"

if msg.is_error_frame:
    eol = "\n"
else:
    eol = " R\n" if msg.is_rx else " T\n"

if msg.is_remote_frame:
    framestr += f"R{eol}"
else:
    if msg.is_fd:
        fd_flags = 0
        if msg.bitrate_switch:
            fd_flags |= CANFD_BRS
        if msg.error_state_indicator:
            fd_flags |= CANFD_ESI
        framestr += f"#{fd_flags:X}"
    framestr += f"{msg.data.hex().upper()}{eol}"

print(framestr)
print(msg)

logger.on_message_received(msg)
logger.stop()
