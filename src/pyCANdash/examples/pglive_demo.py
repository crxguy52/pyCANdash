import cantools.database
import signal

from pglive.sources.data_connector import DataConnector
from pglive.sources.live_plot import LiveLinePlot
from pglive.sources.live_plot_widget import LivePlotWidget, LiveAxisRange

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QApplication, QMainWindow

import can
import cantools

class canPlotterApp(QApplication):

    n_pt_history = 500
    plot_refresh_rate_hz = 60

    interface = 'socketcan'
    channel = 'can1'
    bitrate = 500e3

    plot_title = ''
    signals = {'v_batt':{'pen':'red'},}

    #yRange = LiveAxisRange(fixed_range=[0, 50])    # Fix Y range
    yRange = None   # Auto-range Y

    def __init__(self, dbPath, **kwargs):
        super().__init__([])
        
        self.dbPath = dbPath

        self.mainWindow = QMainWindow()
        self.mainWindow.setStyleSheet(
            """
            QMainWindow {
                background-color: black;
            }
            """
        )       

        self.panel = QtWidgets.QWidget()
        self.layout = QtWidgets.QGridLayout(parent=self.panel) 

        self.plotWidget = LivePlotWidget(
                                        title = self.plot_title,
                                        y_range_controller = self.yRange)
        self.plotWidget.addLegend()

        # Add all of the lines
        self.lines = {}
        self.connectors = {}

        for sig in self.signals:
            self.lines.update({sig:LiveLinePlot(
                                                name = sig,
                                                pen = self.signals[sig]['pen'])})
            self.plotWidget.addItem(self.lines[sig])
            self.connectors.update({sig:
                                DataConnector(
                                    self.lines[sig],
                                    max_points = self.n_pt_history, 
                                    plot_rate = self.plot_refresh_rate_hz)})
                                          

        self.runPauseButton = QtWidgets.QPushButton(text='Pause')
        self.runPauseButton.clicked.connect(self.pause)
        self.yMinBox = QtWidgets.QLineEdit(text='yMin')
        self.yMaxBox = QtWidgets.QLineEdit(text='yMax')        

        self.layout.addWidget(self.plotWidget, 0, 0, 1, 5)
        self.layout.addWidget(self.runPauseButton, 1, 0)
        #self.layout.addWidget(QtWidgets.QLabel(text='yMin'), 1, 1)
        #self.layout.addWidget(self.yMinBox, 1, 2)
        #self.layout.addWidget(QtWidgets.QLabel(text='yMax'), 1, 3)        
        #self.layout.addWidget(self.yMaxBox, 1, 4)        

        self.initCAN()

        self.mainWindow.setCentralWidget(self.panel)
        self.mainWindow.show()

        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        self.exec()        

    def initCAN(self):
        # Open the CAN bus
        self.db = cantools.database.load_file(self.dbPath)

        # Create a dictionary correlating signal name to units
        self.sig2unit = {}
        for message in self.db.messages:
            for signal in message.signals:
                self.sig2unit.update({signal.name : signal.unit})

        # Start the bus
        try:
            print('Attempting to open bus')
            self.bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate) 
        except:
            print('failed, opening virtual')
            self.bus = can.Bus(interface='virtual', receive_own_messages=True)
            self.bus.send_periodic(can.Message(arbitration_id = 100, data = [0, 0, 0, 0, 100, 0, 0, 70]), period=0.01)

        self.listener = self.Listener(self.db, self.connectors)
        self.notifier = can.Notifier(self.bus, [self.listener]) 

    def pause(self):
        if self.runPauseButton.text() == 'Pause':
            self.runPauseButton.setText('Resume')
            for con in self.connectors:
                self.connectors[con].pause()
        else:
            self.runPauseButton.setText('Pause')
            for con in self.connectors:
                self.connectors[con].resume()            


    def exit(self):
        self.notifier.stop()
        self.bus.shutdown()
        self.exit(0)   

    class Listener(can.Listener):
        def __init__(self, db, connectors):
            self.t0 = None
            self.db = db
            self.connectors = connectors

        def on_message_received(self, msg):

            if self.t0 is None:
                self.t0 = msg.timestamp

            # Decode it
            decodedDict = self.db.decode_message(msg.arbitration_id, msg.data)

            # Iterate over all of the signals
            for key in decodedDict:
                if key in self.connectors:
                    self.connectors[key].cb_append_data_point(x=msg.timestamp - self.t0, y=decodedDict[key])
    


    


canPlotterApp(dbPath='/home/victorzaccardo/git/pyCANdash/dbc/gmlan_v1.6_decode.dbc')