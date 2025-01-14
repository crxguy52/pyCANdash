from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QGridLayout,
    QTabWidget,
)
from PyQt6.QtCore import QTimer
import PyQt6.sip as sip

import os
import ast
import logging
from datetime import datetime
import time


from pyCANdash.config_system import configCAN, startPlayer, startLogUploader, startBokehServer
from pyCANdash.TallStatusLayout import TallStatusLayout
from pyCANdash.GridStatusLayout import GridStatusLayout
from pyCANdash.DTCStatusLayout import DTCStatusLayout
from pyCANdash.GaugeLayouts import GaugeLayout1
from pyCANdash.utils import handleException


class tabWidget(QTabWidget):
    def __init__(self, guiCfg, logCfg, canChans):
        super(tabWidget, self).__init__()

        self.tab = []
        self.tab.insert(0, tab0Widget(logCfg["tabCfg"][0]['cellCfg'], guiCfg, canChans))
        self.tab.insert(1, tab1Widget(logCfg["tabCfg"][1]["cellCfg"], canChans))
        self.tab.insert(2, tab2Widget(logCfg["tabCfg"][2]["cellCfg"], canChans))
        self.tab.insert(3, tab3Widget(logCfg["tabCfg"][3]['gaugeCfg'], canChans, colStretch=logCfg["tabCfg"][3]['colStretch']))   
        self.tab.insert(4, tab4Widget(logCfg["tabCfg"][4]['colCfg']))  

        self.addTab(self.tab[0], logCfg["tabCfg"][0]['name'])
        self.addTab(self.tab[1], logCfg["tabCfg"][1]['name'])  
        self.addTab(self.tab[2], logCfg["tabCfg"][2]['name'])   
        self.addTab(self.tab[3], logCfg["tabCfg"][3]['name']) 
        self.addTab(self.tab[4], logCfg["tabCfg"][4]['name'])     

        self.setCurrentIndex(logCfg["startTab"])   


class tab0Widget(QWidget):
    def __init__(self, cellCfg, guiCfg, canChans):
        super(tab0Widget, self).__init__()

        self.gridStatusLayout = GridStatusLayout(guiCfg, canChans)
        self.gridStatusLayout.updateCellsFromCfg(cellCfg)
        self.setLayout(self.gridStatusLayout)

    def update(self, vals):
        self.gridStatusLayout.updateCellVals(vals)


class tab1Widget(QWidget):
    def __init__(self, cellCfg, canChans):
        super(tab1Widget, self).__init__()

        self.leftCol = TallStatusLayout()
        self.leftCol.updateFromCfg(cellCfg["leftCol"], canChans)

        self.rightCol = TallStatusLayout()
        self.rightCol.updateFromCfg(cellCfg["rightCol"], canChans)

        self.layout = QGridLayout()
        self.layout.addWidget(self.leftCol, 0, 0)        
        self.layout.addWidget(self.rightCol, 0, 1)   
        
        self.setLayout(self.layout)       

    def update(self, vals):
        self.leftCol.updateVals(vals)
        self.rightCol.updateVals(vals)


class tab2Widget(QWidget):
    def __init__(self, cellCfg, canChans):
        super(tab2Widget, self).__init__()  

        self.leftCol = TallStatusLayout()
        self.leftCol.updateFromCfg(cellCfg["leftCol"], canChans)

        self.rightCol = TallStatusLayout()
        self.rightCol.updateFromCfg(cellCfg["rightCol"], canChans)

        self.layout = QGridLayout()
        self.layout.addWidget(self.leftCol, 0, 0)        
        self.layout.addWidget(self.rightCol, 0, 1)     
        self.setLayout(self.layout)  

    def update(self, vals):
        self.leftCol.updateVals(vals)
        self.rightCol.updateVals(vals)


class tab3Widget(QWidget):
    def __init__(self, gaugeCfg, canChans, colStretch=None):
        super(tab3Widget, self).__init__()   

        self.gaugeLayout = GaugeLayout1(gaugeCfg, canChans, colStretch=colStretch)

        self.layout = QGridLayout()
        self.layout.addWidget(self.gaugeLayout, 0, 0)
        self.setLayout(self.layout) 
   
       
    def update(self, vals):
        self.gaugeLayout.update(vals)
           

class tab4Widget(QWidget):
    def __init__(self, colCfg):
        super(tab4Widget, self).__init__()

        self.tbl = DTCStatusLayout(colCfg)

        self.layout = QGridLayout()
        self.layout.addWidget(self.tbl, 0, 0)    
        self.setLayout(self.layout)       

    def update(self, vals):
        self.tbl.updateVals(vals)


class StatusBar(QLabel):
    def __init__(self, mainWindow):
        super(StatusBar, self).__init__()
        self.mainWindow = mainWindow
        self.setStyleSheet("QLabel{border-top: 1px outset grey;}")
        self.statusHandler = self.StatusHandler(self)

    # Logging handler to update status wiget
    class StatusHandler(logging.Handler):
        def __init__(self, widget):
            logging.Handler.__init__(self)
            self.widget = widget

        def emit(self, record):
            # Append message (record) to the widget
            self.widget.setText("  " + datetime.now().strftime("%d-%b-%Y %H:%M:%S") + ": " + record.message)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Configure the logger
        self.configLogger()

        # Load the GUI config file
        self.guiCfg = self.loadGUIconfig()

        # Load the logger config file
        self.logCfg = self.loadConfig(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config_files", self.guiCfg["LOGGER_CFG"])) + '.py')

        # Play back a file to vcan if a playback file is specified. 
        # Disable logging if playing back a file, otherwise leave it enabled
        logEn = True
        if 'playbackFn' in self.logCfg.keys():
            if self.logCfg['playbackFn'] is not None:
                playbackFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", self.logCfg['playbackFn']))
                logging.info(f'Playing back {playbackFilePath}')
                self.playbackDict = startPlayer(playbackFilePath)

                # Disable logging if we're playing back a file
                logEn = False

        # Configure the CAN buses - store them in a dictionary
        self.canChans = {}
        for chan in self.logCfg['canChans']:
            canCfg = self.logCfg['canChans'][chan]
            self.canChans[chan] = configCAN(canCfg, self.logCfg['dbcDir'], self.rxCAN, logEn=logEn)

        # Delete the temporary files we created last time for downloading
        for filename in os.listdir(self.logCfg['resDir']):

            fpath = os.path.join(self.logCfg['resDir'], filename)
            lastModTime = os.path.getmtime(fpath)
            oldFlag = lastModTime < (time.time() - 24*60*60)
            zeroSizeFlag = os.path.getsize(fpath) < 145 # empty BLF files are 145 bytes
            fileExtFlag = '.blf' in filename or '.log' in filename

            # Delete the file if it's an export file ('_wide.csv' in the filename) OR
            # If it's more than a day old AND it's zero size
            if '_wide.csv' in filename or (oldFlag and zeroSizeFlag and fileExtFlag):
                logging.warning(f'Deleting {filename}')
                os.remove(self.logCfg['resDir'] + filename)           

        # Start the auto-uploader if it's enabled
        if self.logCfg['logUploader']['ip'] is not None:
            self.logUploader = startLogUploader(self.logCfg['logUploader'], self.logCfg['resDir'])

        # Start the bokeh server if it's enabled
        if self.logCfg['bokehServer']['enable'] is True:
            self.bokehServer = startBokehServer(self.logCfg['resDir'], self.logCfg['dbcDir'], self.logCfg['bokehServer'])

        # Set the window title and size
        self.setWindowTitle("pyCANdash")
        self.setMinimumSize(self.guiCfg["WINDOW_SIZE_MIN_WIDTH"], self.guiCfg["WINDOW_SIZE_MIN_HEIGHT"])

        # Create instances of each of the layouts
        self.mainLayout = QGridLayout()
        self.tabWidget = tabWidget(self.guiCfg, self.logCfg, self.canChans)        
        self.statusBar = StatusBar(self)

        # Create a dictionary to store the current CAN status in
        self.statusDict = {}

        # Connect the tab change to an event
        self.tabWidget.currentChanged.connect(self.tabChanged)
        self.tabIdx = 0     # Starts at 0 by default

        # Add them to the main layout
        tabrow = 0
        statusBarRow = 1

        self.mainLayout.addWidget(self.tabWidget, tabrow, 0)
        self.mainLayout.addWidget(self.statusBar, statusBarRow, 0)

        # Configure the size and stretch of each grid item
        self.mainLayout.setRowStretch(tabrow, 1)        
        self.mainLayout.setRowStretch(statusBarRow, 0)
        self.mainLayout.setRowMinimumHeight(tabrow, 50)

        # Set the initial status
        self.statusBar.setText(" Initialized")

        # Set margins
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        widget = QWidget()
        widget.setLayout(self.mainLayout)
        self.setCentralWidget(widget)

        # Add the status bar to the logger. This happens after everthing else bc when the
        # logger is initially configured the statusbar doesn't exist
        stathandlr = self.statusBar.StatusHandler(self.statusBar)
        stathandlr.setFormatter(self.logFormatter)
        logging.getLogger().addHandler(self.statusBar.statusHandler)
        logging.getLogger().addHandler(stathandlr)   

        # Configure the timer to display info
        self.dispTimer = QTimer()
        self.dispTimerInterval = int(1000/self.logCfg["tabCfg"][0]["dispHz"])
        logging.info('Setting display interval to %i ms' % self.dispTimerInterval)
        self.dispTimer.setInterval(self.dispTimerInterval)
        self.dispTimer.timeout.connect(self.updateDisplay)
        self.dispTimer.start()            

    # Start maximized
    def showEvent(self, event):
        self.showMaximized()        

    def configLogger(self):
        # Configure the logger
        self.logFormatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%d-%b-%Y %H:%M:%S")

        # Log to the console
        stderr_log_handler = logging.StreamHandler()
        stderr_log_handler.setFormatter(self.logFormatter)

        # Start a log file
        logFileName = f"{datetime.now():%Y-%m-%d_%H-%M-%S}" + ".log"
        logFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "logfiles", logFileName))
        #logging.info(f"Logging to {logFilePath}")
        self.logFileHandler = logging.FileHandler(logFilePath)      
        self.logFileHandler.setFormatter(self.logFormatter)       

        # Add both handlers to the root logger so it's accessable in the module
        logging.getLogger().addHandler(stderr_log_handler)
        logging.getLogger().addHandler(self.logFileHandler)          
        logging.getLogger().setLevel("INFO")  


    def loadGUIconfig(self):
        # Load the GUI configuration
        GUICFGPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config_files", "gui_config.py"))
        if os.path.isfile(GUICFGPATH) is True:
            # load it
            logging.info(f"Loading GUI config file {GUICFGPATH}")
            file = open(GUICFGPATH)
            guiCfg = ast.literal_eval(file.read())
            file.close()

            return guiCfg
        else:
            logging.error("Couldn't load GUI Config!")   
            return None     


    def loadConfig(self, filePath):
        # Load the specified config file, return the dictionary

        try:
            if os.path.isfile(filePath) is True:
                # load it
                file = open(filePath)
                configDict = ast.literal_eval(file.read())
                file.close()
            else:
                logging.error("Config file does not exist!")
                configDict = None

            # Define results file paths
            configDict["resDir"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", *self.guiCfg["DATA_DIR"])) + "/"

            # Define where the CAN databases live
            configDict["dbcDir"] = (
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", *self.guiCfg["DBC_DIR"])) + "/"
            )

            return configDict

        except Exception:
            logging.error("Error loading config file %s" % filePath)
            handleException()
            return None


    def rxCAN(self, sender, statusDict, msgCount):
        # If the received dictionary is not empty
        if statusDict:
            # Recieve the latest status and store it for later display
            self.statusDict[sender] = statusDict

        if msgCount is not None:
            # Update the display with how many messages we've recieved 
            self.statusBar.setText(f" {sender} recieved {msgCount:1.0f} messages")
            pass


    def updateDisplay(self):
        # If the display interval is different on the current tab, update the display interval
        tabIdx = self.tabWidget.currentIndex()
        interval = int(1000/self.logCfg["tabCfg"][tabIdx]["dispHz"])

        if self.dispTimer.interval() != interval:
            logging.info('Setting display interval to %i ms' % self.dispTimerInterval)        
            self.dispTimer.setInterval(interval)

        # Update the tab that's currently displayed
        self.tabWidget.tab[tabIdx].update(self.statusDict)


    def tabChanged(self, tabIdx):
        # Update stuff when the tab changes
        logging.info('Tab changed to %i' % tabIdx)


    def closeEvent(self, event):
        # Shut down all the devices
        self.shutdownDevices()

        # Close the app
        event.accept()


    def shutdownDevices(self):
        # Stop all the timers
        logging.info("Stopping all workers")
        
        chans = list(self.canChans.keys())
        for chan in chans:
            worker = self.canChans[chan]['worker']
            if not sip.isdeleted(worker):
                logging.info(f"Stopping worker {self.canChans[chan]['name']}")
                worker.stopSignal.emit()

        # Shut down the loguploader
        if hasattr(self, 'logUploader'):
            if not sip.isdeleted(self.logUploader['worker']):
                logging.info(f"Stopping logUploader worker")
                self.logUploader['worker'].stopSignal.emit()

                # Shut down the loguploader
        if hasattr(self, 'bokehServer'):
            if not sip.isdeleted(self.bokehServer['worker']):
                logging.info(f"Stopping bokehServer worker")
                self.bokehServer['worker'].stopSignal.emit()