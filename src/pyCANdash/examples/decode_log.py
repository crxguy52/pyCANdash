import cantools
import cantools.database
import sys
import logging
from bokeh.plotting import figure, show, output_file, save
from bokeh.io import curdoc
from bokeh.models import HoverTool

def handleException():
    # Handle errors raised by the script and log them
    exc_type, exc_value, exc_traceback = sys.exc_info()
    # Ignore keyboard interrupts so a console program can exit with ctrl + c
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logging.error("Uncaught exception: ", exc_info=(exc_type, exc_value, exc_traceback))

db = cantools.database.load_file('Z:/My Drive/fastboi/guiv2/dbc/gmlan_v1.4.dbc')

fpath = 'Z:/My Drive/fastboi/guiv2/data/'
fn = '20241110_214805.log'
#fn = '20241110_215158.log'
#fn = '20241110_215513.log'

sigName1 = 'accelerator_actual_pos'
sigName2 = 'throttle_pos'
#sigName = 'throttle_pos_valid'

with open(fpath + fn, 'r') as f:
    lines = f.readlines()

    decoded_messages = []
    noDecode = []
    DTCs = {}
    d = {}

for line in lines:
    timestamp, interface, data, txRx = line.split(' ')

    arbID, payload = data.split('#')


    arbID = int(arbID, 16)
    data = bytes.fromhex(payload)  # Remove the '0x' prefix

    if arbID not in noDecode:
        try:
           message = db.get_message_by_frame_id(arbID)
           decoded_data = message.decode(data)

           if arbID == 1906:
                # DTCs
                if decoded_data['diag_trouble_code_triggered'] > -1:
                    DTCs.update({decoded_data['diag_trouble_code_number']: decoded_data})
           else:
                decoded_messages.append({'timestamp': timestamp, **decoded_data})
                for sig in decoded_data:
                    d.update({sig:decoded_data[sig]})

        except KeyError:
            print(f"Message with ID 0x{arbID:03x}, {arbID} not found in DBC.")
            noDecode.append(arbID)

        except:
            print(f"Error decoding ID 0x{arbID:03x}, {arbID}")
            handleException()
            noDecode.append(arbID)

#for v in sorted(d.items()):
#    print(f"{v[0]}: {d[v[0]]}")

t1 = []
val1 = []

t2 = []
val2 = []

for msg in decoded_messages:
    if sigName1 in msg:
        t1.append(float(msg['timestamp'][1:-1]))
        val1.append(msg[sigName1])

for msg in decoded_messages:
    if sigName2 in msg:
        t2.append(float(msg['timestamp'][1:-1]))
        val2.append(msg[sigName2])

t1 = [pt - t1[0] for pt in t1]
t2 = [pt - t2[0] for pt in t2]

curdoc().theme = "dark_minimal"
p = figure(
    title=fn,
    x_axis_label='t, seconds',
    y_axis_label='val',
    sizing_mode="stretch_both"
    )
h = HoverTool()
h.tooltips = "@x, @y"
p.add_tools(h)

p.line(t1, val1, legend_label=sigName1)
p.line(t2, val2, legend_label=sigName2)
show(p)

print('done')

