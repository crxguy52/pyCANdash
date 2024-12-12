"""Main entry point to application.
"""
import sys
from PyQt6.QtWidgets import QApplication
from pyCANdash.layouts import MainWindow

# TODO:
# Start up \ shut down based on car power


def mainApp():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    mainApp()
