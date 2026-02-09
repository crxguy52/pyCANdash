from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,   
    QWidget,
    QLabel,
    QGridLayout,
    QTabWidget,
    QProgressBar,
    QFrame,
)
from PyQt6.QtCore import QTimer, QThread
from PyQt6.QtGui import QKeySequence, QShortcut
import PyQt6.sip as sip

import os
import ast
import logging
from datetime import datetime
import time


from pyCANdash.config_system import configCAN, startPlayer, startLogUploader, startBokehServer, startGPIOmonitor, startHttpServer 
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
        # self.tab.insert(4, tab4Widget(logCfg["tabCfg"][4]['colCfg']))  # DTC doesn't do what I thought it did so I'm disabling it

        self.addTab(self.tab[0], logCfg["tabCfg"][0]['name'])
        self.addTab(self.tab[1], logCfg["tabCfg"][1]['name'])  
        self.addTab(self.tab[2], logCfg["tabCfg"][2]['name'])   
        self.addTab(self.tab[3], logCfg["tabCfg"][3]['name']) 
        # self.addTab(self.tab[4], logCfg["tabCfg"][4]['name'])     

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


class StatusBar(QFrame):
    def __init__(self, mainWindow):
        super(StatusBar, self).__init__()
        self.mainWindow = mainWindow
        #self.statusHandler = self.StatusHandler(self)
        progBarWidth = 75

        self.layout = QGridLayout()
        self.setLayout(self.layout) 

        self.can0ProgressBar = QProgressBar()
        self.can0ProgressBar.setRange(0, 4000) # Set the range for 0% to 100%. at 500kbaud 4k messages is 100%
        self.can0ProgressBar.setValue(0)     
        self.can0ProgressBar.setTextVisible(False)
        self.can0ProgressBar.setFixedWidth(progBarWidth)  

        self.can1ProgressBar = QProgressBar()
        self.can1ProgressBar.setRange(0, 4000) # Set the range for 0% to 100%. at 500kbaud 4k messages is 100%
        self.can1ProgressBar.setValue(0)     
        self.can1ProgressBar.setTextVisible(False)
        self.can1ProgressBar.setFixedWidth(progBarWidth)  

        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.Shape.HLine)

        self.statusLabel = QLabel('')
        self.odoLabel = QLabel(str(-1))

        self.layout.addWidget(self.divider, 0, 0, 1, 6)

        progBarStretch = 1
        
        self.layout.addWidget(QLabel('can0:'), 1, 0)
        self.layout.setColumnStretch(0, 0)      
        
        self.layout.addWidget(self.can0ProgressBar, 1, 1)
        self.layout.setColumnStretch(1, progBarStretch)  
        
        self.layout.addWidget(QLabel('can1:'), 1, 2)
        self.layout.setColumnStretch(2, 0)        
        
        self.layout.addWidget(self.can1ProgressBar, 1, 3)        
        self.layout.setColumnStretch(3, progBarStretch)  
        
        self.layout.addWidget(self.statusLabel, 1, 4)
        self.layout.setColumnStretch(4, 100)

        self.layout.addWidget(self.odoLabel, 1, 5)
        self.layout.setColumnStretch(5, 0)  

        self.layout.setHorizontalSpacing(15)
        self.layout.setVerticalSpacing(0)

    
    def setText(self, text):
        self.statusLabel.setText(text)

    def setProgress(self, canChan:str, value:int):
        if canChan.lower().strip() == 'can0':
            self.can0ProgressBar.setValue(value)
        elif canChan.lower().strip() == 'can1':
            self.can1ProgressBar.setValue(value)
        else:
            logging.warning(f'StatusBar: can channel {canChan} not recognized, bus load not updated')

    def setOdometer(self, val:float):
        self.odoLabel.setText(f"{val:.1f} mi")


    # Logging handler to update status wiget
    class StatusHandler(logging.Handler):
        def __init__(self, widget):
            logging.Handler.__init__(self)
            self.widget = widget

        def emit(self, record):
            # Append message (record) to the widget
            #self.widget.setText("  " + datetime.now().strftime("%d-%b-%Y %H:%M:%S") + ": " + record.message)
            self.widget.setText(record.message)

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Add ctrl + c shortcut to close the application 
        self.shortcut_close = QShortcut(QKeySequence("Ctrl+C"), self)
        self.shortcut_close.activated.connect(self.close)
        
        # Set the background as black and text as white
        self.setStyleSheet("color: white; background-color: black;")

        # Load the GUI config file
        self.guiCfg = self.loadGUIconfig()

        # Load the logger config file
        self.logCfg = self.loadConfig(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config_files", self.guiCfg["LOGGER_CFG"])) + '.py')

        # Set the data directory
        internalDir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
        if self.logCfg['dataDir'] is not None:
            if os.path.isdir(self.logCfg['dataDir']):
                # If the directory exists, use it
                self.dataDir = self.logCfg['dataDir']
                logStr = f'Using data directory: {self.dataDir}'
            else:
                # Use the internal data directory
                self.dataDir = internalDir
                logStr = f'Specified data directory not valid, using internal data directory: {self.dataDir}'
        else:
            # Use the internal data directory
            self.dataDir = internalDir
            logStr = f'Using internal data directory: {self.dataDir}'

        # Configure the logger after we set the data directory so we can log to the correct directory
        self.configLogger(self.dataDir)
        logging.info(logStr)

        # Play back a file to vcan if a playback file is specified. 
        # Disable logging if playing back a file, otherwise leave it enabled
        logEn = True
        if 'playbackFn' in self.logCfg.keys():
            if self.logCfg['playbackFn'] is not None:
                playbackFilePath = os.path.abspath(os.path.join(self.dataDir, self.logCfg['playbackFn']))
                logging.info(f'Playing back {playbackFilePath}')
                self.playbackDict = startPlayer(playbackFilePath)

                # Disable logging if we're playing back a file
                logEn = False
        
        # Load the odometer value if enabled and we're not doing a playback
        if self.logCfg['odometer']['enable'] and logEn is True:        

            # Load the odometer file and initialize it to the correct value
            self.odoPath = os.path.abspath(os.path.join(self.dataDir, "odometer.txt"))

            try:
                # If the file doesn't exist, create it and initalize to zero
                if not os.path.isfile(self.odoPath):
                    with open(self.odoPath, "w") as f:
                        f.write("0")
                        f.flush()
                        os.fsync(f.fileno()) # Force write to physical media
                        self.odometer = 0
                else:
                    with open(self.odoPath, "r") as f:
                        self.odometer = float(f.read())

                # Initialize last time to zero
                self.odometer_t_last = datetime.now()
                self.odometer_speed_last = 0
                self.odometer_distance_last_written = self.odometer    
            except:
                logging.error('Error loading or creating odometer file, disabling')
                self.logCfg['odometer']['enable'] = False

        # Configure the CAN buses - store them in a dictionary
        self.canChans = {}
        for chan in self.logCfg['canChans']:
            canCfg = self.logCfg['canChans'][chan]
            self.canChans[chan] = configCAN(canCfg, self.logCfg['dbcDir'], self.rxCAN, self.dataDir, logEn=logEn)

        # Delete the temporary files we created last time for downloading
        for filename in os.listdir(self.dataDir):

            fpath = os.path.join(self.dataDir, filename)
            lastModTime = os.path.getmtime(fpath)
            oldFlag = lastModTime < (time.time() - 24*60*60)
            zeroSizeFlag = os.path.getsize(fpath) < 145 # empty BLF files are 145 bytes
            fileExtFlag = '.blf' in filename or '.log' in filename

            # Delete the file if it's an export file ('_wide.csv' in the filename) OR
            # If it's more than a day old AND it's zero size
            if '_wide.csv' in filename or (oldFlag and zeroSizeFlag and fileExtFlag):
                logging.warning(f'Deleting {filename}')
                os.remove(self.dataDir + filename)   

        # Start the GPIO monitor 
        if self.logCfg['GPIOmonitor']['Enable']:
            self.GPIOmonitor = startGPIOmonitor(self.logCfg['GPIOmonitor'], self.GPIOshutdownStatus)  
        else:
            logging.info('GPIO monitoring is disabled')     
        
        self.exitCode = 0       # Default to not shutting down when we exit
        
        # Start the auto-uploader if it's enabled
        if self.logCfg['logUploader']['ip'] is not None:
            self.logUploader = startLogUploader(self.logCfg['logUploader'], self.dataDir)

        # Start the bokeh server if it's enabled
        if self.logCfg['bokehServer']['enable'] is True:
            self.bokehServer = startBokehServer(self.dataDir, self.logCfg['dbcDir'], self.logCfg['bokehServer'])

        if self.logCfg['httpServer']['enable'] is True:
            self.httpServer = startHttpServer(self.dataDir, self.logCfg['httpServer'])

        # Set the window title and size
        self.setWindowTitle("pyCANdash")
        self.setMinimumSize(self.guiCfg["WINDOW_SIZE_MIN_WIDTH"], self.guiCfg["WINDOW_SIZE_MIN_HEIGHT"])

        # Create instances of each of the layouts
        self.mainLayout = QGridLayout()
        self.tabWidget = tabWidget(self.guiCfg, self.logCfg, self.canChans)        
        self.statBar = StatusBar(self)      # Dont' call it statusbar since that's a property of QMainWindow

        # Create a dictionary to store the current CAN status in
        self.statusDict = {}

        # Connect the tab change to an event
        self.tabWidget.currentChanged.connect(self.tabChanged)
        self.tabIdx = 0     # Starts at 0 by default

        # Add them to the main layout
        tabrow = 0
        statBarRow = 1

        self.mainLayout.addWidget(self.tabWidget, tabrow, 0)
        self.mainLayout.addWidget(self.statBar, statBarRow, 0)

        # Configure the size and stretch of each grid item
        self.mainLayout.setRowStretch(tabrow, 1)        
        self.mainLayout.setRowStretch(statBarRow, 0)
        self.mainLayout.setRowMinimumHeight(tabrow, 50)

        # Set the initial status
        self.statBar.setText(" Initialized")

        # Set margins
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        widget = QWidget()
        widget.setLayout(self.mainLayout)
        self.setCentralWidget(widget)

        # Add the status bar to the logger. This happens after everthing else bc when the
        # logger is initially configured the statBar doesn't exist
        stathandlr = self.statBar.StatusHandler(self.statBar)
        stathandlr.setFormatter(self.logFormatter)
        #logging.getLogger().addHandler(self.statusBar.statusHandler)
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

    def configLogger(self, dataDir):
        # Configure the logger
        self.logFormatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%d-%b-%Y %H:%M:%S")

        # Log to the console
        stderr_log_handler = logging.StreamHandler()
        stderr_log_handler.setFormatter(self.logFormatter)

        # Start a log file
        logFileName = f"{datetime.now():%Y-%m-%d_%H-%M-%S}" + ".log"

        # If the logfile directory doesn't exist, create it
        logDir = os.path.abspath(os.path.join(self.dataDir, "logfiles"))
        if not os.path.isdir(logDir):
            os.mkdir(logDir)
        
        logFilePath = os.path.abspath(os.path.join(logDir, logFileName))
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
            #logging.info(f"Loading GUI config file {GUICFGPATH}")
            file = open(GUICFGPATH)
            guiCfg = ast.literal_eval(file.read())
            file.close()

            return guiCfg
        else:
            #logging.error("Couldn't load GUI Config!")   
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

        # If the odometer is enabled and we have the right signal, keep track of it
        if self.logCfg['odometer']['enable'] and self.logCfg['odometer']['signalName'] in statusDict and hasattr(self, 'odometer'):

            # Calculate the distance traveled since last time
            speed_now = statusDict[self.logCfg['odometer']['signalName']]
            avg_speed =  ( speed_now + self.odometer_speed_last) / 2
            self.odometer_speed_last = speed_now
            
            # Speed is usually given in miles or kilometers per hour so convert this to hours
            now = datetime.now()
            dt = (now - self.odometer_t_last).total_seconds() / 3600
            self.odometer_t_last = now
            dx = avg_speed * dt

            # Convert from km to miles
            # TODO: base this on the actual units, not a hardxoded number
            dx_miles = dx * 0.621371
            self.odometer += dx_miles

            self.statBar.setOdometer(self.odometer)

            distance_delta = self.odometer - self.odometer_distance_last_written

            if distance_delta > 1:
                
                # Write the new value to the odometer file
                # Save it to a temp file first, then copy over to the real file to avoid corruption
                path_temp = self.odoPath + '.tmp'
                with open(path_temp, 'w') as f:
                    f.write(str(self.odometer))
                    f.flush()
                    os.fsync(f.fileno()) # Force write to physical media

                #Atomic rename (POSIX standard guarantees this is atomic)
                # If power fails here, you either have the old file or the new one, never a half-written one.
                os.replace(path_temp, self.odoPath)                      

                # Update the last distance traveled value
                self.odometer_distance_last_written = self.odometer     

        if msgCount is not None:
            # Update the display with how many messages we've recieved 
            #self.statusBar.setText(f" {sender} recieved {msgCount:1.0f} messages")
            self.statBar.setProgress(self.logCfg['canChans'][sender]['channel'], msgCount * self.logCfg['canChans'][sender]['RxHz'])


    def updateDisplay(self):
        # If the display interval is different on the current tab, update the display interval
        tabIdx = self.tabWidget.currentIndex()
        interval = int(1000/self.logCfg["tabCfg"][tabIdx]["dispHz"])

        if self.dispTimer.interval() != interval:
            #logging.info('Setting display interval to %i ms' % self.dispTimerInterval)        
            self.dispTimer.setInterval(interval)

        # Update the tab that's currently displayed
        self.tabWidget.tab[tabIdx].update(self.statusDict)


    def tabChanged(self, tabIdx):
        # Update stuff when the tab changes
        #logging.info('Tab changed to %i' % tabIdx)
        pass


    def GPIOshutdownStatus(self, val):
        if val >= 1:
            self.exitCode = 1
            self.close()


    def closeEvent(self, event):
        # Shut down all the devices
        self.shutdownDevices()

        # Close the app
        event.accept()
        QApplication.instance().exit(self.exitCode) 
        
        
    def shutdownDevices(self):

        if self.logCfg['odometer']['enable'] and logEn is True: 
            logging.info('Recording odometer value')
            with open(self.odoPath, "w") as f:
                f.write(self.odometer)
                f.flush()
                os.fsync(f.fileno()) # Force write to physical media
        
        # Stop all the timers
        logging.info("Stopping all workers")
        threads = {}
        
        chans = list(self.canChans.keys())
        for chan in chans:
            worker = self.canChans[chan]['worker']
            if not sip.isdeleted(worker):
                logging.info(f"Stopping worker {self.canChans[chan]['name']}")
                worker.stopSignal.emit()
                threads.update({self.canChans[chan]['name']: self.canChans[chan]['thread']})

        # Shut down the loguploader
        if hasattr(self, 'logUploader'):
            if not sip.isdeleted(self.logUploader['worker']):
                logging.info(f"Stopping logUploader worker")
                #self.logUploader['worker'].stopFlag = True
                self.logUploader['worker'].stopSignal.emit()
                threads.update({'logUploader': self.logUploader['thread']})

        # Shut down the bokeh server
        if hasattr(self, 'bokehServer'):
            if not sip.isdeleted(self.bokehServer['worker']):
                logging.info(f"Stopping bokehServer worker")
                self.bokehServer['worker'].stopSignal.emit()
                #self.bokehServer['worker'].stopFlag = True
                # the boke server is blocking so stop() never gets called...
                # just shut down anyways. not the right way to do it but it works
                #threads.update({'bokehServer': self.bokehServer['thread']})

        if hasattr(self, 'GPIOmonitor'):
            if not sip.isdeleted(self.GPIOmonitor['worker']):
                logging.info(f"Stopping GPIOmonitor worker")
                self.GPIOmonitor['worker'].stopSignal.emit()
                threads.update({'GPIOmonitor': self.GPIOmonitor['thread']})

        if hasattr(self, 'httpServer'):
            if not sip.isdeleted(self.httpServer['worker']):
                logging.info(f"Stopping httpServer worker")
                self.httpServer['worker'].stopSignal.emit()
                # Tell it to stop but don't wait for it to end, this likes to hang
                # Not the right way to do it but it works
                #threads.update({'httpServer': self.httpServer['thread']})

        t_start = datetime.now()

        # Wait for all the threads to close
        while True:
            if len(threads) == 0:
                break

            for thread in list(threads.keys()):
                if threads[thread].isRunning():
                    logging.info(f'shutdownDevices: Waiting for {thread} to stop')
                else:
                    logging.info(f'shutdownDevices: {thread} stopped')
                    threads.pop(thread)
                
            # Just quit if it's hanging 
            if (datetime.now() - t_start).total_seconds() > 1:
                logging.info(f'shutdownDevices: Shutdown time exceeded 1 second, force stopping')
                break

            time.sleep(50e-3)
                
        








