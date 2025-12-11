"""Main entry point to application.
"""
import sys, logging, os
from PyQt6.QtWidgets import QApplication
from pyCANdash.layouts import MainWindow


def mainApp():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    exit_code = app.exec() 

    if exit_code == 0:
        # Normal exit, don't do anything
        logging.info('Application closed, shutdown not requested')

    elif exit_code == 1:
        # Car has been powered off, shut down the system
        logging.info('Closing application and shutting down')

        # Only shutdown linux systems, not windows
        if sys.platform == 'win32':
            logging.info('Shutdown requested but not executed because this is a windows machine')
        else: # Linux/Mac
            os.system("shutdown -h now")
    


if __name__ == "__main__":
    mainApp()
