''' 
Use the ``bokeh serve`` command to run the example by executing:

    bokeh serve ./src/pycandash/examples/bokeh_server_example2.py 

at your command prompt. Then navigate to the URL

    http://localhost:5006/

in your browser.

'''

import os
import glob
from typing import Any
import cantools
import can
import sys
import logging
from functools import partial
import socket

from bokeh.layouts import column, row, layout
from bokeh.models import ColumnDataSource, MultiSelect, Dropdown, Range1d, LegendItem, Button, CustomJS
from bokeh.plotting import figure
from bokeh.palettes import Category10
from bokeh.models.widgets import Paragraph, Div
from tornado.web import StaticFileHandler

from bokeh.server.server import Server


class SigSelectAndPlot():
    def __init__(self, source, name='0', other_x_range=None):
        super(SigSelectAndPlot, self).__init__()
        self.logDict = {}
        self.source = source
        self.other_x_range = other_x_range
        self.name = name
        self.N_LINES = 10

        # Create the figure
        if other_x_range is None:
            self.fig = figure(
                            min_width=400,
                            sizing_mode='stretch_both',
                            tools="hover,pan,reset,save,wheel_zoom,box_zoom,",
                            active_drag = 'pan',
                            active_inspect = None,
                            active_tap = None,
                            name=name,
                            )
        else:
            self.fig = figure(
                            min_width=400,
                            sizing_mode='stretch_both',
                            tools="hover,pan,reset,save,wheel_zoom,box_zoom,",
                            active_drag = 'pan',
                            active_inspect = None,
                            active_tap = None,                            
                            name=name,
                            x_range = other_x_range,
                            )

        # Create the multiselect for selecting signals
        self.sigSelect = MultiSelect(
            options=[], 
            sizing_mode="stretch_height", 
            min_width=300, 
            width_policy='min')

        # Link a change in the sigselect to update the plot
        self.sigSelect.on_change('value', self.update_plot)

        # Create the blank lines to be updated
        colors = Category10[self.N_LINES]
        self.lines = []
        for i in range(0, self.N_LINES):
            self.lines.append(
                self.fig.line(
                    x='timestamp', 
                    y='y', 
                    source=self.source, 
                    legend_label='', 
                    visible=False, 
                    color=colors[i]))

        self.fig.legend.location = 'bottom_right'
        self.fig.legend.click_policy = 'hide'

    def update_plot(self, attrname, old, new):
        # Update the lines and legend
        legendItems = []
        minVal= None
        maxVal = None
        for i in range(0, self.N_LINES):
            if i < len(new):
                self.lines[i].glyph.x = 'timestamp'
                self.lines[i].glyph.y = new[i]
                self.lines[i].visible = True
                legendItems.append(LegendItem(label=new[i], renderers=[self.lines[i]]))
                minVal = min(j for j in self.source.data[new[i]] + [minVal] if j is not None)
                maxVal = max(j for j in self.source.data[new[i]] + [maxVal] if j is not None)
            else:
                self.lines[i].visible = False

        self.fig.legend.items = legendItems

        # Handle the case where minVal and maxVal are the same
        if minVal is None or maxVal is None:
            if minVal is None:
                yMin = -1
            if maxVal is None:
                yMax = 1        
        elif minVal == maxVal:
            yMin = minVal - 1
            yMax = maxVal + 1

        else:
            rng = maxVal - minVal
            yMin = minVal - rng * 0.1
            yMax = maxVal + rng * 0.1
            
        # Re-scale the figure
        # Don't re-scale x since it breaks the link
        #if self.other_x_range is None:
        #    self.fig.x_range = Range1d(min(self.logDict['timestamp']), max(self.logDict['timestamp']))
        #    pass
        #else:
        #    self.fig.x_range = self.other_x_range
        #    pass

        self.fig.y_range = Range1d(yMin, yMax)

    def update_sigList(self, sigList):
        self.sigSelect.options = sigList      

    def update_title(self, title):
        self.fig.title.text = title
  

class FileDropDown():
    def __init__(self, dataDir):
        super(FileDropDown, self).__init__()
        
        self.dataDir = dataDir

        # Create a dropdown with a list of the files
        self.obj = Dropdown(
            label='Select Log to View', 
            button_type='primary', 
            menu=[], 
            min_width=400, 
            sizing_mode='stretch_width')

    def update_values(self):
        # Refresh the files in the directory
        files = []
        for file in [os.path.basename(x) for x in sorted(glob.glob(self.dataDir + '*.*'))]:
            files.append([file, file])

        self.obj.menu = files


class PresetDropDown():
    def __init__(self):
        super(PresetDropDown, self).__init__()

        self.menu = [ 
            # Display Name                  Value
            ("Engine Temps and pressures",  "engine_temps_and_pressures"),
            ("Accelerator and throttle",    "accelerator_and_throttle"),
            ("Torque requests",             "torque_requests"),
            ("Clear Selections",            "clear_selection"),
            ]        

        self.obj = Dropdown(            
            label='Preset Views',
            menu = self.menu, 
            button_type='default', 
            min_width=300, 
            width_policy='min') 


    def get_selected(self, preset):

            #("Engine Temps and pressures",  "engine_temps_and_pressures"),
            #("Accelerator and throttle",    "Accelerator_and_throttle"),
            #("Torque requests",             "torque_requests"),
            #("Clear Selections",            "clear_selection"),
            #("four",                        "four"),

        presetDict = {
            'engine_temps_and_pressures':[
                    ['engine_speed', 'engine_max_speed_limit'],
                    ['engine_oil_pressure'],
                    ['engine_coolant_temp', 'engine_oil_temperature', 'trans_oil_temp', 'ambient_air_temp'],
            ],
            'accelerator_and_throttle':[
                ['engine_speed', 'engine_max_speed_limit'],
                ['accelerator_actual_pos', 'throttle_pos'],
                ['barometric_pressure_abs', 'engine_manifold_abs_pres'],
            ],
            'torque_requests':[
                [],
                [],
                [],
            ],
            'clear_selection':[
                [],
                [],
                [],
            ],            
        }

        return presetDict[preset]
        

class CsvButton():
    def __init__(self, logDict, dataPath, fileDropDown, doc):
        super(CsvButton, self).__init__()

        self.logDict = logDict
        self.dataPath = dataPath
        self.fileDropDown = fileDropDown
        self.doc = doc

        # Create the button
        self.obj = Button(label='Download CSV table')

        # Create a dummy object to trigger events in the correct sequence:
        #   Changing the min_width will trigger a download event
        # Create the wide file, Send the file to the client

        # https://discourse.bokeh.org/t/execute-both-python-server-side-and-customjs-code-at-a-callback/9074/4
        self.dummyDiv = Div(text='', min_width=1, visible=False)

        # When the csvButton is pressed, save to csv
        # https://stackoverflow.com/questions/64615215/download-an-excel-file-from-bokeh-server-via-button

        self.fileSendCallback = CustomJS(args=dict(fileDropDown=self.fileDropDown), code="""
        var csvFn = fileDropDown.label.slice(0, -4) + '_wide.csv';
        console.log(csvFn);

        fetch('/data/' + csvFn, {cache: "no-store"}).then(response => response.blob())
                        .then(blob => {
                            //addresses IE
                            if (navigator.msSaveBlob) {
                                navigator.msSaveBlob(blob, csvFn);
                            }

                            else {
                                var link = document.createElement("a");
                                link.href = URL.createObjectURL(blob);
                                
                                link.download = csvFn;
                                link.target = "_blank";
                                link.style.visibility = 'hidden';
                                link.dispatchEvent(new MouseEvent('click'))
                                URL.revokeObjectURL(URL);
                            }
                        });
        """
        )

        # When the button is clicked, create the wide format file
        self.obj.on_click(self.create_wide_format)

        # When the dummyDiv's min_width will trigger a download event
        self.dummyDiv.js_on_change('min_width', self.fileSendCallback) 

    def create_wide_format(self, event):
        # Convert the dictionary to a wide format and save it to a csv
        logging.info('Writing CSV')
        csvName = self.fileDropDown.label[0:-4] + '_wide.csv'
        with open(self.dataPath + csvName, 'w', newline="") as f:
            # Write the header
            # Make a list of the keys with timestamp being first
            keys = [key for key in sorted(self.logDict.keys()) if key != 'timestamp']
            keys.insert(0, 'timestamp')

            # Print the header
            for i in range(0, len(keys)):
                key = keys[i]
                f.write(key + ',')
            f.write('\n')

            for i in range(0, len(self.logDict['timestamp'])):
                for j in range(0, len(keys)):
                    key = keys[j]
                    var = self.logDict[key][i]
                    if var is not None:
                        f.write(str(var) + ',')
                    else:
                        f.write('"",')
                f.write('\n')            

        logging.info('CSV write complete')

        # Trigger the download
        self.dummyDiv.min_width += 1

        # Temp files get deleted at app startup


class LogButton():
    def __init__(self, dataPath, fileDropDown):
        super(LogButton, self).__init__()

        self.dataPath = dataPath
        self.fileDropDown = fileDropDown

        # Create the button
        self.obj = Button(label='Download log file')

        # When the csvButton is pressed, save to csv
        # https://stackoverflow.com/questions/64615215/download-an-excel-file-from-bokeh-server-via-button

        self.fileSendCallback = CustomJS(args=dict(fileDropDown=self.fileDropDown), code="""
        var logFn = fileDropDown.label;
        console.log(logFn);

        fetch('/data/' + logFn, {cache: "no-store"}).then(response => response.blob())
                        .then(blob => {
                            //addresses IE
                            if (navigator.msSaveBlob) {
                                navigator.msSaveBlob(blob, logFn);
                            }

                            else {
                                var link = document.createElement("a");
                                link.href = URL.createObjectURL(blob);
                                
                                link.download = logFn;
                                link.target = "_blank";
                                link.style.visibility = 'hidden';
                                link.dispatchEvent(new MouseEvent('click'))
                                URL.revokeObjectURL(URL);
                            }
                        });
        """
        )

        # When the button is clicked, create the wide format file
        self.obj.js_on_click(self.fileSendCallback)       


class MainLayout():
    def __init__(self, dataDir, dbcDir, doc, arbIDdtc=1906, n_plots=3):
        super(MainLayout, self).__init__()  
        self.dataDir = dataDir
        self.dbcDir = dbcDir
        self.doc = doc
        self.arbIDdtc = arbIDdtc
        self.logfilename = ''
        self.logDict = {}
        self.N_PLOTS = n_plots

        # Delete the temporary files we created last time for downloading
        for filename in os.listdir(self.dataDir):
            if '_wide.csv' in filename:
                logging.info(f'Deleting {filename}')
                os.remove(self.dataDir + filename)

        # Create variables
        self.files = []     # List of files in the data directory
        self.source = ColumnDataSource(data={'timestamp':[0,1], 'y':[0,0]})

        # Create the objects
        self.fileDropDown = FileDropDown(self.dataDir)
        self.presetDropDown = PresetDropDown()

        self.plots = []
        self.plots_layout = []
        for i in range(0, self.N_PLOTS):
            if i > 0:
                other_x_range = self.plots[0].fig.x_range
            else:
                other_x_range = None
                
            self.plots.append(SigSelectAndPlot(self.source, name=str(i), other_x_range=other_x_range))
            self.plots_layout.append(
                row([self.plots[i].sigSelect, self.plots[i].fig],
                 sizing_mode='stretch_both', height_policy='max', width_policy='max'))

        # When a new file is selected, load the new file
        self.fileDropDown.obj.on_click(self.load_data_callback)
        self.presetDropDown.obj.on_click(self.set_preset)

        self.DTCtext = Paragraph(text="DTCs present in this log: ")
        self.statusText = Div(text='<b>Initialized<b>', sizing_mode='stretch_width')
        self.statusTextLabel = Paragraph(text='Status: ')
        self.csvButton = CsvButton(self.source.data, self.dataDir, self.fileDropDown.obj, self.doc)
        self.logButton = LogButton(self.dataDir, self.fileDropDown.obj,)

        # Put them in a layout
        self.layout = layout(
                        [
                            row(self.fileDropDown.obj, self.logButton.obj, self.csvButton.obj, self.csvButton.dummyDiv, self.presetDropDown.obj, sizing_mode='stretch_width'),
                            row(self.statusTextLabel, self.statusText, self.DTCtext, sizing_mode='stretch_width'),
                            column(self.plots_layout, sizing_mode='stretch_both'),
                        ], sizing_mode='stretch_both'
                    )


    def load_data_callback(self, event):
        # We need to split this up into a callback and a a function to do the actual work, 
        # otherwise the status text won't update until this callback finishes. See 
        # https://discourse.bokeh.org/t/updating-widgets-and-force-refreshing-the-interface/4364/2
        logging.info(f'Loading {event.item}')
        self.statusText.text = f'<b>Loading {event.item}<b>'
        self.fileDropDown.obj.label = event.item
        self.doc.add_next_tick_callback(partial(self.load_data, event))

    def load_data(self, event):
        # Load the selected file
        self.logDict, DTCs = self.log2dict(self.dataDir + event.item, self.dbcDir + 'gmlan_v1.4_decode.dbc')
        self.csvButton.logDict = self.logDict

        # Update the multiselect values
        logging.info('Creating multselect keys')
        sigList = [[key, key] for key in sorted(self.logDict.keys())]

        # Update the data sources
        logging.info(f'Updating data source')
        self.source.data = self.logDict        

        for plot in self.plots:
            # Update all the sig select boxes
            logging.info(f'Updating signal list for plot {plot.name}')
            plot.update_sigList(sigList)

            # Update the plots to auto-range them
            plot.update_plot(None, None, plot.sigSelect.value)

            # Update the plot titles
            #logging.info(f'Updating title for plot {plot.name}')
            #plot.update_title(event.item)

        # Update the DTCs in this log
        logging.info(DTCs)
        DTCtext = 'DTCs present in this log: '
        for code in DTCs:
            DTCtext += f'p{code:04}, '
        logging.info(f'DTCs present in log file: {DTCs}')
        self.DTCtext.text = DTCtext

        self.statusText.text = f'<b>{event.item} loaded<b>'

    def set_preset(self, event):
        try:
            selected = self.presetDropDown.get_selected(event.item)

            for i in range(0, len(selected)):
                #logging.info(selected[i])
                self.plots[i].sigSelect.value = selected[i]
                self.plots[i].update_plot(None, None, selected[i])
        except Exception as e:
            logging.info(e)

    def log2dict(self,
        log_file_path: str,
        db_file_path: str,
        sample_time_ms: int = 10,
        fill_val = None,
    ) -> dict:
        """Read a CAN file and convert it to a dictionary at fixed time steps

        Rows of the dictionary will be spaces sample_time_ms apart, and each row will have the latest value for each signal
        up to that timestamp.

        Args:
            log_file_path: file name of log file to decode
            db_file_path: file path to the database file
            timestamp_col: column name of the timestamp to use for pivoting
            sample_time_ms: sample time of each row in milliseconds
        """

        # Load the database file
        db = cantools.database.load_file(db_file_path)

        noDecode = []   # Arbitration IDs not in the database
        decoded = []    # List of lists of decoded data. One entry is [timestamp, signal, value]
        sigNames = []   # A list of unique signals in the log
        DTCs = []       # A list of DTCs present in the log file

        # Iterate over the log file and decode all the messages
        logging.info('Decoding messages')
        for msg in can.LogReader(log_file_path):
            if msg.arbitration_id not in noDecode:
                    try:
                        dbMessage = db.get_message_by_frame_id(msg.arbitration_id)
                        signals = dbMessage.decode(msg.data)

                        # If this is the first message we're decoding, take note of the time
                        #  and subtract it from all others
                        if len(decoded) == 0:
                            t0 = msg.timestamp

                        for signal in signals:
                            # Add it to the list
                            decoded.append([msg.timestamp - t0, signal, self.tryConvert2float(signals[signal])])
                            TIMESTAMP_COL = 0
                            SIGNAME_COL = 1
                            VAL_COL = 2

                            if signal not in sigNames:
                                sigNames.append(signal)

                        # if it's a DTC, log it to the DTCs list
                        if msg.arbitration_id == self.arbIDdtc:
                            if signals['diag_trouble_code_triggered'] > 0 and signals['diag_trouble_code_number'] not in DTCs:
                                    DTCs.append(signals['diag_trouble_code_number'])

                    except KeyError:
                        # Skip it next time if there was an error decoding
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        logging.info(f'Couldnt decode ArbID {msg.arbitration_id} ({f"0x{msg.arbitration_id:02x}"}), skipping')
                        noDecode.append(msg.arbitration_id)
                    except Exception as e:
                        logging.error(e)


        # Append timestamp to signal names
        sigNames.append('timestamp')

        currentValues: dict[str, Any]   = {key:fill_val for key in sigNames}  # Current values for the row we're in
        dict_out                        = {key:[] for key in sigNames}  # Dictionary that gets returned, initialize all values to -1
        increment = sample_time_ms / 1000

        logging.info("Creating output dictionary")
        next_row_timestamp = 0
        for row in decoded:

            timestamp = row[TIMESTAMP_COL]

            if next_row_timestamp is None:
                # determine the first row timestamp as the next round sample_time ms increment
                next_row_timestamp = increment

            elif timestamp > next_row_timestamp:
                # since each row will have the latest value up to that timestamp, as soon as we go past that
                # timestamp we are done with that row, so write the row, and increment timestamp
                currentValues["timestamp"] = next_row_timestamp

                # Write the current values to the dictionary
                for key in currentValues:
                    dict_out[key].append(currentValues[key])

                # Find the next row value
                while next_row_timestamp <= timestamp:
                    # find next timestamp increment greater than current timestamp
                    next_row_timestamp += round(increment, 3)
            
            # Update the currentValues dictionary
            currentValues[row[SIGNAME_COL]] = row[VAL_COL]

        # write the last row -- there will always be at least one more value received since last write
        if next_row_timestamp is not None:
            currentValues["timestamp"] = next_row_timestamp 

        # Write the current values to the dictionary
        for key in currentValues:
            dict_out[key].append(currentValues[key])

        return dict_out, DTCs

    def tryConvert2float(self, val :str):
        try:
            val = float(val)
        except:
            val = str(val)

        return val



# Get the local IP address
def get_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('10.254.254.254', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP
    


def bkapp(doc, dataDir=None, dbcDir=None):
    # https://docs.bokeh.org/en/latest/docs/user_guide/server/library.html
    ml = MainLayout(dataDir, dbcDir, doc)

    # Update files in the dropdown directory once a second
    doc.add_periodic_callback(ml.fileDropDown.update_values, 1000)
    doc.add_root(ml.layout)
    doc.title = "pyCANdash Viewer"



if __name__ == "__main__":
    # Add the data directory to the web server's static path so we can use it to download files from
    # https://github.com/bokeh/bokeh/blob/3.6.2/examples/server/api/tornado_embed.py

    dataDir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")), "")
    dbcDir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "dbc")), "")

    server = Server({'/': partial(bkapp, dataDir=dataDir, dbcDir=dbcDir)},
                    allow_websocket_origin=[get_ip()+":5006", "localhost:5006"],
                    extra_patterns=[(r'/data/(.*)', StaticFileHandler, {'path': dataDir}),],
                    )
    server.start()

    # Reconfigure bokeh logger to the correct format
    logging.basicConfig(
                    level = logging.INFO,
                    format = "%(levelname)s: %(asctime)s - %(message)s",
                    force=True)

    logging.info('Starting on ' + get_ip() + ' and localhost')    

    # server.io_loop.add_callback(server.show, "/")
    server.io_loop.start()

    #server.io_loop.stop()

    # TODO:
    # Resample rate dropdown
    # Move deleting of temp files to main app before server starts
    # Add server to GUI