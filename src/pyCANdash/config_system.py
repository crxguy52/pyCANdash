#from beta.visa_instr_ctrl.rigol_mso5x import ScopeObj
#from beta.hvir_control.workers import camWorker, CANWorker, faultInitWorker, scopeWorker, cDAQWorker
from PyQt6.QtCore import QThread
import sys
import logging

from pyCANdash.workers import CANWorker, CANplayerWorker, logUploaderWorker
import cantools


def configCAN(canCfg, dbcDir, statusFcn, logEn=True):

    # Initialize the CAN port if the interface isn't None
    if canCfg['interface'] is not None:
        logging.info(f'Initializing {canCfg["name"]} on {canCfg["interface"]}')

        logging.info(f'{canCfg["name"]}: Loading database')
        canCfg['db'] = cantools.database.load_file(dbcDir + canCfg['dbcName'] + '.dbc')

        canCfg['sig2unit'] = {}
        # Create a dictionary correlating signal name to units
        logging.info(f'{canCfg["name"]}: Creating signal name to units dictionary')
        for message in canCfg['db'].messages:
            for signal in message.signals:
                canCfg['sig2unit'].update({signal.name : signal.unit})

        # Create thread and worker
        logging.info(f'{canCfg["name"]}: Starting thread')
        canCfg['thread'] = QThread()

        if logEn is False:
             logging.info(f'Playing back file, forcing {canCfg["name"]} to use virtual bus')
             canCfg['interface'] = 'usevitual'

        logging.info(f'{canCfg["name"]}: Starting CANWorker')
        canCfg['worker'] = CANWorker(canCfg, logEn=logEn)

        # Start it upppp
        startThread(canCfg['thread'], canCfg['worker'], statusFcn)

    else:
        logging.error(f'{canCfg["name"]}: Device not specified, skipping')
    
    return canCfg


def startPlayer(logFile, printDebug=False):
        # Need to assign this to a variable in the main thread or else
        # it gets deleted and the GUI crashes
        playbackDict = {}

        # Create thread and worker
        logging.info(f'Playback: Creating thread')
        playbackDict['thread'] = QThread()

        logging.info(f'Playback: Starting CANplayerWorker')
        playbackDict['worker'] = CANplayerWorker(logFile, printDebug)

        # Start it upppp
        logging.info('Playback: Starting thread')
        startThread(playbackDict['thread'], playbackDict['worker'], None)
        
        return playbackDict


def startLogUploader(FTPcfg, resDir):
    # Need to assign this to a variable in the main thread or else
    # it gets deleted and the GUI crashes
    logUploader = {}

    logging.info('FTP: Creating thread')
    logUploader['thread'] = QThread()

    logging.info('FTP: Creating worker')
    logUploader['worker'] = logUploaderWorker(FTPcfg['ip'], FTPcfg['remoteLogDir'], resDir)

    # Start it upppp
    logging.info('Playback: Starting thread')
    startThread(logUploader['thread'], logUploader['worker'], None)

    return logUploader

     
def startThread(thread, worker, statusFcn):
    # Move them to the thread - do this before making connections!!
    worker.moveToThread(thread)

    # Connect the status signals
    worker.initConnections(statusFcn)

    # Run the worker when the thread starts
    thread.started.connect(worker.run)

    # When the worker finishes, quit the thread and delete thread and worker
    worker.finishedSignal.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    worker.finishedSignal.connect(thread.quit)    

    # Start the thread
    thread.start()


