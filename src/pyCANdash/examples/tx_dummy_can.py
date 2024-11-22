import can
import cantools
import time
import random

# can0 and can1 are automatically loaded by following this guide:
# https://www.beyondlogic.org/adding-can-controller-area-network-to-the-raspberry-pi/
# To automatically bring up the interface on boot, edit your /etc/network/interfaces file and add the following:
# auto can0
# iface can0 inet manual
#     pre-up /sbin/ip link set can0 type can bitrate 500000 triple-sampling on restart-ms 100
#     up /sbin/ifconfig can0 up
#     down /sbin/ifconfig can0 down

# 
# os.system('sudo ip link set can0 up type can bitrate 1000000 dbitrate 8000000 restart-ms 1000 berr-reporting on fd on')
# os.system('sudo ip link set can1 up type can bitrate 1000000 dbitrate 8000000 restart-ms 1000 berr-reporting on fd on')

can0 = can.interface.Bus(channel = 'can0', interface = 'socketcan', fd=True)
# can1 = can.interface.Bus(channel = 'can1', interface = 'socketcan', fd=True)


dbPath = "./config_files/gmlan_v1.4.dbc"

db = cantools.database.load_file(dbPath)

fakeRPM = 4e3

# Create a GMLAN message
# Start by getting a blank message
cantoolsMsg = db.get_message_by_name('engine_general_status_1')

# Fill in zero for all of the values
vals = {}
for sig in cantoolsMsg.signals:
    vals[sig.name] = 0


while fakeRPM < 8000:

    vals['engine_speed'] = fakeRPM
    pycanMsg = can.Message(\
                arbitration_id = cantoolsMsg.frame_id,\
                data = cantoolsMsg.encode(vals),
                is_extended_id=False)

    can0.send(msg=pycanMsg)
    time.sleep(0.01)
    # rcv = can1.recv(timeout=1.0)
    # print(rcv)
    fakeRPM += int(100 * random.random()) - 49
    # print(fakeRPM)
    #print('sent 1 messages')

can0.shutdown()
# can1.shutdown()


# try:

#     msg = can.Message(is_extended_id=True, is_fd=True, arbitration_id=0x123, data=[0, 1, 2, 3, 4, 5, 6, 7])
#     for i in range(0, 10):
#         can0.send(msg)
#         time.sleep(0.1)
#         rcv = can1.recv(timeout=1.0)
#         print(rcv)
# except Exception as e:
#     print(e)

# can0.shutdown()
# can1.shutdown()


# os.system('sudo ifconfig can0 down')
# os.system('sudo ifconfig can1 down')
