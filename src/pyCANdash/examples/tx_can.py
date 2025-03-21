import can
import cantools
import time



dbPath = "/home/victorzaccardo/git/pyCANdash/dbc/gmlan_v1.5.dbc"

print("Loading " + dbPath)
db = cantools.database.load_file(dbPath)

print("Connecting to " + 'can1')
bus = can.interface.Bus(channel = 'can1', interface = 'socketcan', fd=False)



def create_message(db, msgName, sigName, sigVal):

    # Create a GMLAN message
    # Start by getting a blank message
    cantoolsMsg = db.get_message_by_name(msgName)

    # Fill in zero for all of the values
    vals = {}
    for msg in cantoolsMsg.signals:
        vals[msg.name] = 0

    vals[sigName] = sigVal

    return can.Message(\
                arbitration_id = cantoolsMsg.frame_id,\
                data = cantoolsMsg.encode(vals),
                is_extended_id=False)



n_to_tx = 215
n_tx = 0

if 0: 
    while n_to_tx + 1 > n_tx:
        rpmMsg = create_message(db, 'engine_general_status_1', 'eng_speed', (8000/216) * n_tx)
        bus.send(msg=rpmMsg)

        speedMsg = create_message(db, 'vehicle_speed_and_distance', 'vehicle_speed_avg_driven', 2 * n_tx)
        bus.send(speedMsg)

        coolMsg = create_message(db, 'engine_general_status_4', 'eng_coolant_temp', n_tx)
        bus.send(coolMsg)

        oilPmsg = create_message(db, 'engine_general_status_5', 'eng_oil_pressure', 1020 * n_tx/n_to_tx)
        bus.send(oilPmsg)

        oilPmsg = create_message(db, 'engine_general_status_5', 'check_engine_ind_on', n_tx % 2)
        bus.send(oilPmsg)                                                         

        print('sent %1.0f messages' % n_tx)
        time.sleep(0.05)
        n_tx += 1

else:
        rpmMsg = create_message(db, 'engine_general_status_1', 'eng_speed', 8000)
        bus.send(msg=rpmMsg)
        time.sleep(0.10)

        speedMsg = create_message(db, 'vehicle_speed_and_distance', 'vehicle_speed_avg_driven', 15/0.6213712)
        bus.send(speedMsg)
        time.sleep(0.10)

        coolMsg = create_message(db, 'engine_general_status_4', 'eng_coolant_temp', 100)
        bus.send(coolMsg)
        time.sleep(0.10)

        oilPmsg = create_message(db, 'engine_general_status_5', 'eng_oil_pressure', 50*6.894)
        bus.send(oilPmsg)
        time.sleep(0.10)

        # CELmsg = create_message(db, 'engine_general_status_5', 'check_engine_ind_on', 1)
        # bus.send(CELmsg)    

bus.shutdown()
