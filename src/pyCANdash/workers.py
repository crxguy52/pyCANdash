
import pyCANdash.config_system as configSys
from pyCANdash.bokeh_classes import bkapp, get_ip
import logging
from PyQt6.QtCore import pyqtSignal, QTimer, QObject, pyqtSlot
import os.path as path
from datetime import datetime

import time
import can
from typing import Iterable, cast
import os 
import glob
import ftplib
from functools import partial
import functools
import threading

from gpiozero import InputDevice

from tornado.web import StaticFileHandler
from bokeh.server.server import Server

import http.server
import socketserver



CAN_MSG_EXT = 0x80000000
CAN_ERR_FLAG = 0x20000000
CAN_ERR_BUSERROR = 0x00000080
CAN_ERR_DLC = 8

CANFD_BRS = 0x01
CANFD_ESI = 0x02

class CANWorker(QObject):
    statusSignal = pyqtSignal(str, dict, int)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()
    _stop_event = threading.Event()     

    def __init__(self, canCfg, dataDir, logEn=True):
        QObject.__init__(self)
        self.canCfg = canCfg
        self.dataDir = dataDir
        self.logEn = logEn

        # Create a dictionary to store current status of recieved data in
        self.statusDict = {'DTCs':{}}

        # Create a list of arbitration IDs to decode
        self.arbID2decode = []

    def initConnections(self, statusFcn):
        # Connect the status signal to update the appropriate statusCell
        self.statusSignal.connect(statusFcn)

        # Stop the worker when the stop signal is recieved
        self.stopSignal.connect(self.stop)

        # TODO: Do we want to connect initi finished signal to anything?
        # Connect the finished signal to enabling the run button
        # self.initFinishedSignal.connect(self.mainWindow.configRunLayout.checkEnableRun)

    def run(self):
        try:                
            # Start the bus
            try:
                self.bus = can.Bus(interface=self.canCfg['interface'], channel=self.canCfg['channel'], bitrate=self.canCfg['baud'])
                logging.info(f'{self.canCfg["name"]}: {self.canCfg["interface"]} opened')
            except:
                self.bus = can.Bus(interface='virtual')
                logging.info(f'{self.canCfg["name"]}: Hardware not available, using virtual CAN')

            if self.logEn:
                # Start the log file
                logFileName = f"{self.canCfg['name']}_{datetime.now():%Y-%m-%d_%H-%M-%S}.{self.canCfg['logFormat']}"
                self.logFilePath = path.abspath(path.join(self.dataDir, logFileName)) 
                logging.info(f'{self.canCfg["name"]}: Logging CAN data to ' + self.logFilePath)
                self.logger = can.Logger(self.logFilePath)

            # Create the list of arbiration IDs we know how to decode
            for msg in self.canCfg['db'].messages:
                self.arbID2decode.append(msg.frame_id)

            # Create a timer that polls the status and updates the status cell
            logging.info(f'{self.canCfg["name"]}: Starting status timer')
            self.timer = QTimer(self)

            self.statusInterval = 1 / self.canCfg['RxHz']
            logging.info(f'{self.canCfg["name"]}: Setting CAN RX interval to {1e3*self.statusInterval} ms')
            self.timer.setInterval(int(1e3 * self.statusInterval))  
            self.timer.timeout.connect(self.queryStatus)
            self.timer.start()        

            logging.info(f'{self.canCfg["name"]}: Init finisehd')
            self.initFinishedSignal.emit()

        except Exception:
            logging.error(f'{self.canCfg["name"]}: Unable to open {self.canCfg["interface"]} or virtual bus')

            self.logger = None

            configSys.handleException()
            self.stop()

    def queryStatus(self):

        message_count = 0
        t_end = time.time() + self.statusInterval

        # Recieve the message from the CAN bus and log it. 
        # Do it until we time out or there are no more messages to recieve
        while time.time() < t_end:
            msg = self.bus.recv(timeout=0)       

            if msg is not None:

                if self.logEn:
                    self.logger.on_message_received(msg)

                message_count += 1

                # If it's in the CAN database, decode the message
                if msg.arbitration_id in self.arbID2decode:

                    # Decode it
                    decodedDict = self.canCfg['db'].decode_message(msg.arbitration_id, msg.data)

                    # If it's not a DTC, put it in the decodedDict
                    if msg.arbitration_id != self.canCfg['arbIDdtc']:
                        
                        # Iterate over all of the signals
                        for key in decodedDict:
                            if key not in self.statusDict:
                                # If the key isn't in the results dictionary, add they key and value
                                self.statusDict.update({key:decodedDict[key]})
                            else:
                                # Otherwise it's in the dictionary, so update the value
                                self.statusDict[key] = decodedDict[key]       
                    else:
                        # It's a DTC so store it seperately
                        if decodedDict['diag_trouble_code_number'] not in self.statusDict['DTCs']:
                            # if it's not in the DTCs dictionary, add it
                            self.statusDict['DTCs'].update({decodedDict['diag_trouble_code_number']: decodedDict})
                        else:
                            # Otherwise update it
                            self.statusDict['DTCs'][decodedDict['diag_trouble_code_number']] = decodedDict

            else:
                break

        if message_count > 0:
            # Send it to the main thread
            self.statusSignal.emit(self.canCfg["name"], self.statusDict, message_count)
        else:
            self.statusSignal.emit(self.canCfg["name"], {}, message_count)

    @pyqtSlot()
    def stop(self):
        logging.info(f'{self.canCfg["name"]}: Stopping')

        if hasattr(self, 'timer'):
            logging.info(f'{self.canCfg["name"]}: Stopping status timer')
            self.timer.stop()
            self.timer.deleteLater()

        # Close the CAN connection
        logging.info(f'{self.canCfg["name"]}: Shutting down bus')
        if hasattr(self, "bus"):
            self.bus.shutdown()
            if hasattr(self, 'logger'):
                if self.logger is not None:
                    self.logger.stop()
            logging.info(f'{self.canCfg["name"]}: Bus shut down')

        # Clean up
        logging.info(f'{self.canCfg["name"]}: Worker stopped')
        self.finishedSignal.emit()

        # This shouldn't be necessary since I thread.quit gets linked to finishedSignal when the thread
        # is created, but it looks like finishedSignal never gets received in the main thread for some reason          
        self.thread().quit()        


class CANplayerWorker(QObject):
    statusSignal = pyqtSignal(str, dict, int)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()
    _stop_event = threading.Event()     

    def __init__(self, logFile, printDebug=False):
        QObject.__init__(self)

        self.logFile = logFile
        self.printDebug = printDebug

    def initConnections(self, statusFcn):
        # Stop the worker when the stop signal is recieved
        #self.stopSignal.connect(self.stop)
        pass

    def run(self):
        try:
            # Create a virtual bus using the same interface
            logging.info('Starting bus')
            with can.Bus(interface='virtual') as bus:

                logging.info(f'Opening LogReader {self.logFile}')
                with can.LogReader(self.logFile) as reader:

                    logging.info('Creating sync')
                    in_sync = can.MessageSync(cast(Iterable[can.Message], reader), skip=5)

                    logging.info(f"Can LogReader (Started on {datetime.now()})")

                    for message in in_sync:
                        if message.is_error_frame:
                            continue
                        if self.printDebug:
                            logging.info(message)
                        bus.send(message)

            logging.info('Playback finished')
            self.finishedSignal.emit()
        except:
            configSys.handleException()


class logUploaderWorker(QObject):
    statusSignal = pyqtSignal(str, dict, int)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()
    _stop_event = threading.Event()    

    def __init__(self, ip, remoteLogDir, localDir):
        QObject.__init__(self)

        self.ip = ip
        self.remoteLogDir = remoteLogDir
        self.localDir = localDir

    def initConnections(self, statusFcn):
        # Stop the worker when the stop signal is recieved
        self.stopSignal.connect(self.stop)


    def run(self):
        # Wait 10 seconds to give the PC a chance to connecto to wifi
        logging.info("logUploader: Waiting 10 seconds for wifi to connect")
        t0 = datetime.now()
        while (datetime.now() - t0).total_seconds() < 10:
            if self._stop_event.is_set():
                break
            time.sleep(0.1)

        # Connect to the FTP server
        self.ftp = self.connect2ftp(self.ip)

        if self.ftp is not None:      
            try:  
                # Change the the logging directory
                self.ftp.cwd(self.remoteLogDir)

                # Send the CAN logs
                self.copyFiles('', '')

                # Send the GUI log files
                self.copyFiles('/logfiles/', 'logfiles')
                    
                logging.info("logUploader: Finished syncing files, closing")
                self.ftp.close()
            except Exception as e:
                logging.error(f'logUploader: Unable to sync files: {e}')
                try:
                    self.ftp.close()
                except:
                    pass

        self.stop()        


    def connect2ftp(self, ip, username=None, password=None):
        # Try to connect to the server for 30 seconds
        t_end = time.time() + 30
        while time.time() < t_end and self._stop_event.is_set() == False:
            try:
                logging.info(f"logUploader: Connecting to {ip}")
                ftp = ftplib.FTP(ip, username, password, timeout=0.75)
                ftp.login()
                logging.info(f'logUploader: Connected to {ip}')
                return ftp
            except:
                # Wait for 5 seconds
                t0 = datetime.now()
                while (datetime.now() - t0).total_seconds() < 5:
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)

        if 'ftp' not in locals():
            if self._stop_event.is_set():
                logging.info('logUploader: FTP connection aborted due to stopFlag')
            else:
                logging.info('logUploader: Unable to connect to FTP server, aborting') 

            return None


    def copyFiles(self, relRemoteDir, relLocalDir):
        # relRemoteDir is relative path to the established remote directory
        # relLocalDir is relative path to the established local directory

        # Change the remote directory to the one we're looking for
        if len(relRemoteDir) > 0:
            self.ftp.cwd(self.remoteLogDir + '/' + relRemoteDir)        

        # Get a list of what exists in the remote directory
        remoteList = self.ftp.nlst()

        # Make sure the local and remote directories have trailing slashes
        localDir = os.path.join(self.localDir, relLocalDir, '')

        logging.info(f'logUploader: Comparing {localDir} to {relRemoteDir}')

        for file in [os.path.basename(x) for x in glob.glob(localDir + '*.*')]:
            if self._stop_event.is_set():
                logging.info('logUploader: Stopping upload due to stopFlag')
                break
            
            dT = self.getSecondsDelta(file)
            dT_thresh = 5*60    # 5 minutes
            
            # If the current file isn't in the remote directory AND it was created
            # more than 5 minute ago (IE, not the file we're writing to now), send it over
            # TODO: Add file size check here. If local file is larger than remote file, overwrite the remote file
            if file not in remoteList and dT > dT_thresh:

                fullPath = localDir + file

                # Only upload it if it's not empty - an empty BLF file is 145 bytes
                if os.path.getsize(fullPath) > 145: 

                    with open(fullPath, 'rb') as f:

                        logging.info(f'logUploader: Sending {fullPath}')
                        status = self.ftp.storbinary(f"STOR {file}", f)
                        logging.info(f'logUploader: {file}: {status}')
                        
                else:
                    logging.info(f'logUploader: {file} was 0 bytes, skipping')
                    
            elif dT < dT_thresh:
                logging.info(f'logUploader: {file} was created {dT} seconds ago (less than {dT_thresh}), skipping')

        # Change remote directory back to the default
        self.ftp.cwd(self.remoteLogDir)

    @pyqtSlot()
    def stop(self):
        logging.info(f'LogUploader: Stopping')

        if hasattr(self, 'ftp'):
            if self.ftp is not None:
                self.ftp.close()

        # Clean up
        logging.info(f'LogUploader: Worker stopped')
        self.finishedSignal.emit()   

        # This shouldn't be necessary since I thread.quit gets linked to finishedSignal when the thread
        # is created, but it looks like finishedSignal never gets received in the main thread for some reason          
        self.thread().quit()


    def getSecondsDelta(self, fn:str):
        # Determine how long ago the file was created based on the name
    
        import re
        try:
            parts = re.split('_|\.', fn)     
            datestr = parts[-3] + '_' + parts[-2]
            seconds = (datetime.now() - datetime.strptime(datestr, '%Y-%m-%d_%H-%M-%S')).seconds   
        except Exception as e:
            logging.error(f'logUploader: Could not determine how long ago {fn} was created: {e}')
            seconds = -1
    
        return seconds


class bokehServerWorker(QObject):
    statusSignal = pyqtSignal(str, dict, int)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()
    _stop_event = threading.Event() 

    def __init__(self, dataDir, dbcPath, IPs):
        QObject.__init__(self)

        self.dataDir = dataDir
        self.dbcPath = dbcPath
        self.IPs     = IPs


    def initConnections(self, statusFcn):
        # Stop the worker when the stop signal is recieved
        self.stopSignal.connect(self.stop)


    def run(self):
        # Add the data directory to the web server's static path so we can use it to download files from
        # https://github.com/bokeh/bokeh/blob/3.6.2/examples/server/api/tornado_embed.py

        # Wait 10 seconds to give the PC a chance to connecto to wifi
        t0 = datetime.now()
        while (datetime.now() - t0).total_seconds() < 10:
            if self._stop_event.is_set():
                logging.info(f'bokehServer: stopping due to _stop_event')
                break        
            time.sleep(0.1)

        if self._stop_event.is_set() == False:
            ipList = [get_ip()+":5006", "localhost:5006"] + self.IPs
            logging.info(f'bokehServer: Starting on {ipList}')           

            self.server = Server({'/': partial(bkapp, dataDir=self.dataDir, dbcPath=self.dbcPath)},
                            allow_websocket_origin=ipList,
                            extra_patterns=[(r'/data/(.*)', StaticFileHandler, {'path': self.dataDir}),],
                            )

            self.server.start()
            self.server.io_loop.start()

            # TODO:
            # io_loop.start() is blocking so stop() never gets called, it just gets killed. Fix this.    


    @pyqtSlot()
    def stop(self):

        logging.info(f'bokehServer: Stopping server')
        if hasattr(self, 'server'):
            self.server.io_loop.stop()

        # Clean up
        logging.info(f'bokehServer: Worker stopped')
        self.finishedSignal.emit()   

        # This shouldn't be necessary since I thread.quit gets linked to finishedSignal when the thread
        # is created, but it looks like finishedSignal never gets received in the main thread for some reason          
        self.thread().quit()  


class gpioMonitorWorker(QObject):
    statusSignal = pyqtSignal(float)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()
    _stop_event = threading.Event() 

    def __init__(self, gpioPin, lowTime=5, Ts=40e-3):
        QObject.__init__(self)

        self.gpioPin = gpioPin  # GPIO pin number to monitor
        self.lowTime = lowTime  # How long the pin must be low before we shut down
        self.Ts = Ts            # How often to sample the pin (seconds)

        self.lowCountMax = int(self.lowTime / self.Ts)
        self.lowCount_minus1 = self.lowCountMax - int(1/self.Ts)
        self.lowCount_minus2 = self.lowCountMax - int(2/self.Ts)
        self.lowCount_minus3 = self.lowCountMax - int(3/self.Ts)

        try:
            self.pinDevice = InputDevice(self.gpioPin, pull_up=True, active_state=True)
        except:
            logging.info(f'gpioMonitorWorker: Failed to open pin device on GPIO{self.gpioPin}, using dummy device')
            self.pinDevice = self.dummyInputDevice()
        self.lowCount = 0
        self.pinStatus = None
        self.pinStatusLast = None


    def initConnections(self, statusFcn):
        if statusFcn is not None:
            # Connect the status signal to update the appropriate statusCell
            self.statusSignal.connect(statusFcn)

        # Stop the worker when the stop signal is recieved
        self.stopSignal.connect(self.stop)


    def run(self):
        # Create a timer that polls the GPIO status
        logging.info(f'gpioMonitorWorker: Starting status timer')
        self.timer = QTimer(self)

        logging.info(f'gpioMonitorWorker: Setting gpioMonitorWorker interval to {1e3*self.Ts} ms')
        self.timer.setInterval(int(1e3 * self.Ts))  
        self.timer.timeout.connect(self.queryGpio)
        self.timer.start()        

        logging.info(f'gpioMonitorWorker: Init finisehd')
        #self.initFinishedSignal.emit()


    def queryGpio(self):        
        # If the GPIO has been low for the prescribed time emit a shutdown signal (1)
        # Otherwise emit a keep going signal (0)

        self.pinStatusLast = self.pinStatus
        self.pinStatus = self.pinDevice.value()

        if self.pinStatus == False:
            self.lowCount += 1

        else:   # pinStauts is True (high)
            # Reset lowCount
            self.lowCount = 0

        # Send some info messages a few seconds before we shut down
        match self.lowCount:
            case self.lowCount_minus3:
                logging.info('gpioMonitorWorker: Shutting down in 3...')
            case self.lowCount_minus2:
                logging.info('gpioMonitorWorker: Shutting down in 2...') 
            case self.lowCount_minus1:
                logging.info('gpioMonitorWorker: Shutting down in 1...')   
            case self.lowCountMax:
                logging.info('gpioMonitorWorker: Shutting down now byeeee')
        
        self.statusSignal.emit(self.lowCount / self.lowCountMax)

    @pyqtSlot()
    def stop(self):

        logging.info(f'gpioMonitorWorker: Stopping')

        if hasattr(self, 'timer'):
            logging.info(f'gpioMonitorWorker: Stopping status timer')
            self.timer.stop()
            self.timer.deleteLater()

        logging.info(f'gpioMonitorWorker: Worker stopped')
        # Clean up
        self.finishedSignal.emit()  

        # This shouldn't be necessary since I thread.quit gets linked to finishedSignal when the thread
        # is created, but it looks like finishedSignal never gets received in the main thread for some reason          
        self.thread().quit()            


    class dummyInputDevice():
        def __init__(self):
            pass    

        def value(self):
            return False


class httpServerWorker(QObject):
    statusSignal = pyqtSignal(float)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()
    _stop_event = threading.Event() 

    def __init__(self, dataDir, port=8000):
        QObject.__init__(self)

        self.dataDir = dataDir  # Directory to serve 
        self.port = port        # port to serve on
        self.httpd = None       # Reference to the server instance        


    def initConnections(self, statusFcn):
        # Stop the worker when the stop signal is recieved
        self.stopSignal.connect(self.stop)


    def run(self):
        # 1. Configure the handler to serve the specific directory
        # We use partial to pass the 'directory' arg to the SimpleHTTPRequestHandler
        Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.dataDir)

        # 2. Setup the server
        # allow_reuse_address prevents "Address already in use" errors if you restart quickly
        socketserver.TCPServer.allow_reuse_address = True
        
        try:
            with socketserver.TCPServer(("", self.port), Handler) as self.httpd:
                logging.info(f"httpServerWorker: Serving {self.dataDir} at port {self.port}")
                
                # 3. Start the blocking server loop
                # This will block until shutdown() is called in the stop() method
                self.httpd.serve_forever(poll_interval=0.1)
                
        except OSError as e:
            logging.error(f"httpServerWorker: Error starting server: {e}")
        except Exception as e:
            logging.error(f"httpServerWorker: Unexpected error: {e}")
        finally:
            # This block runs when serve_forever() is broken by shutdown()
            logging.info('httpServerWorker: Server loop ended')
            self.finishedSignal.emit()


    @pyqtSlot()
    def stop(self):

        logging.info(f'httpServerWorker: Stopping')

        # Trigger the server to stop accepting requests
        # This waits for all requests to stop and blocks! This is not called for now as it causes the GUi to hang
        if self.httpd:
            if self.httpd.socket:
                logging.info(f'httpServerWorker: Closing socket')
                self.httpd.socket.close()
            
            logging.info(f'httpServerWorker: Shutting down server')
            self.httpd.server_close()

        logging.info(f'httpServerWorker: Worker stopped')
        self.finishedSignal.emit()        

        # This shouldn't be necessary since I thread.quit gets linked to finishedSignal when the thread
        # is created, but it looks like finishedSignal never gets received in the main thread for some reason          
        self.thread().quit()       
        







