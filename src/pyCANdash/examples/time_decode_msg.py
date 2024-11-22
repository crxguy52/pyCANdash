import can
import cantools
import time


db = cantools.database.load_file('Z:/My Drive/fastboi/guiv2/config_files/gmlan_v1.3.dbc')

#dc = self.db.decode_message(msg.arbitration_id, msg.data)

#				# Get the signal name, value, and units. The message name (per the dbc file) is OBD2, and we know the signal name
#				signal_name 	= dc['ParameterID_Service01'].name
#				sqaddr 			= self.sqcfg_inv[signal_name]
#				dispname 		= self.sqcfg[sqaddr]['dispname']
#				signal_value 	= dc[signal_name]
#				signal_unit 	= self.db.get_message_by_name('OBD2').get_signal_by_name(signal_name).unit
#				timestamp 		= msg.timestamp

# https://forum.hptuners.com/showthread.php?88322-GMLAN-canbus-messages
# F9 00004000000000FF
# C9 0000000700400800

databytearray = bytes.fromhex('00004000000000FF')[::-1] # last [] flips the byte array

n_iterations = int(1e5)

t_start = time.time()

for i in range(n_iterations):

    dc = db.decode_message(0x0f9, bytes.fromhex('00004000000000FF')[::-1])
    # fromhex and integer take the same time
    #dc = db.decode_message(0x0f9, 0x00004000000000FF.to_bytes(8, 'big')[::-1])

t_end = time.time()

print('Decoding message took %1.9f us on average' % (1e6 * (t_end - t_start)/n_iterations))

