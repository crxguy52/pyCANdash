
import pyCANdash.config_system as configSys
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

    def __init__(self, canCfg, logEn=True):
        QObject.__init__(self)
        self.canCfg = canCfg
        self.logEn = logEn

        # Create a dictionary to store current status of recieved data in
        self.statusDict = {'DTCs':{}}

        # Create a list of arbitration IDs to decode
        self.arbID2decode = []

    def initConnections(self, statusFcn):
        # TODO: Connect the status signal to update the appropriate statusCell
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
                logFileName = f"{self.canCfg['name']}_{datetime.now():%Y%m%d_%H%M%S}.{self.canCfg['logFormat']}"
                self.logFilePath = path.abspath(path.join(path.dirname(__file__), "..", "..", "data", logFileName)) 
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
        self.finishedSignal.emit()


class CANplayerWorker(QObject):
    statusSignal = pyqtSignal(str, dict, int)
    stopSignal = pyqtSignal()
    initFinishedSignal = pyqtSignal()
    finishedSignal = pyqtSignal()

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

    def __init__(self, ip, remoteLogDir, localDir):
        QObject.__init__(self)

        self.ip = ip
        self.remoteLogDir = remoteLogDir
        self.localDir = localDir

    def initConnections(self, statusFcn):
        # Stop the worker when the stop signal is recieved
        #self.stopSignal.connect(self.stop)
        pass

    def run(self):
        # Connect to the FTP server
        self.ftp = self.connect2ftp(self.ip)

        if self.ftp is not None:        
            # Change the the logging directory
            self.ftp.cwd(self.remoteLogDir)

            # Send the CAN logs
            self.copyFiles('', '')

            # Send the GUI log files
            self.copyFiles('/logfiles/', 'logfiles')
                
            logging.info("logUploader: Finished syncing files, closing")
            self.ftp.close()


    def connect2ftp(self, ip, username=None, password=None):
        # Try to connect to the server for 30 seconds
        t_end = time.time() + 30
        while time.time() < t_end:
            try:
                logging.info(f"logUploader: Connecting to {ip}")
                ftp = ftplib.FTP(ip, username, password, timeout=1)
                ftp.login()
                logging.info(f'logUploader: Connected to {ip}')
                return ftp
            except:
                time.sleep(5)   

        if 'ftp' not in locals():
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
            
            # If the current file isn't in the remote directory, send it over
            if file not in remoteList:

                fullPath = localDir + file

                # Only upload it if it's not empty
                if os.path.getsize(fullPath) > 0:

                    with open(fullPath, 'rb') as f:

                        logging.info(f'logUploader: Sending {fullPath}')
                        status = self.ftp.storbinary(f"STOR {file}", f)
                        logging.info(f'logUploader: {file}: {status}')
                        
                else:
                    logging.info(f'logUploader: {file} was 0 bytes, skipping')

        # Change remote directory back to the default
        self.ftp.cwd(self.remoteLogDir)

    @pyqtSlot()
    def stop(self):
        logging.info(f'LogUploader: Stopping')

        self.ftp.close()

        # Clean up
        self.finishedSignal.emit()   
