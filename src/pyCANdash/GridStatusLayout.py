from PyQt6 import QtCore
import logging
from bisect import bisect_left

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QGridLayout,
)

from pyCANdash.utils import handleException, colorName2hex, findUnit

class GridStatusLayout(QGridLayout):
    def __init__(self, guiCfg, canChans):
        # Create a reference to the main layout
        self.guiCfg = guiCfg
        self.canChans = canChans

        super(GridStatusLayout, self).__init__()

        self.statusCells = {}

        for row in range(0, guiCfg["STATUS_ROWS"]):
            # Maintain even row stretch by stretching them all the same
            self.setRowStretch(row, 1)

            for col in range(0, guiCfg["STATUS_COLS"]):
                addr = "%i,%i" % (row, col)
                self.statusCells.update({addr: StatusCell()})
                self.addWidget(self.statusCells[addr], row, col)

                # Maintain even column spacing by stretching all the columns the same
                self.setColumnStretch(col, 1)

    # Function to update the scope status after a config file is selected
    def updateCellsFromCfg(self, cfgDict):

        self.cfgDict = cfgDict
        self.colors = cfgDict['colors']

        # Update all of the cells from the config file
        try:
            for row in range(0, self.guiCfg["STATUS_ROWS"]):
                for col in range(0, self.guiCfg["STATUS_COLS"]):
                    addr = "%i,%i" % (row, col)

                    if len(cfgDict[addr]['dispName']) > 0:
                        self.statusCells[addr].setName(cfgDict[addr]['dispName'])
                    else:
                        self.statusCells[addr].setName(cfgDict[addr]['sigName'])

                    unit, gain, offset = findUnit(cfgDict[addr]['sigName'], self.canChans, useIps=cfgDict[addr]['convert2ips'])

                    self.statusCells[addr].setVal('-')
                    self.statusCells[addr].setUnits(unit)
                    self.cfgDict[addr]['gain'] = gain
                    self.cfgDict[addr]['offset'] = offset
                    self.statusCells[addr].setBgColor("blue")

        except Exception:
            logging.error("Error loading scope configuration")
            handleException()

    def updateCellVals(self, vals:dict):
        # vals is a dictionary containing as many entries as there are CAN interfaces
        # Each entry contains the latest data from that interface
        # Iterate over the interfaces and update the display
        for valDictKey in vals.keys():
            valDict:dict = vals[valDictKey]

            # Iterate over all the cells
            for row in range(0, self.guiCfg["STATUS_ROWS"]):
                for col in range(0, self.guiCfg["STATUS_COLS"]):
                    addr = "%i,%i" % (row, col)

                    sigName = self.cfgDict[addr]['sigName']

                    # If there's a new value, update the display value
                    if sigName in valDict.keys():
                        val = valDict[sigName]

                        if type(val) is int or type(val) is float:
                            # if it's a number, convert it to a string
                            calVal = valDict[sigName] * self.cfgDict[addr]['gain'] + self.cfgDict[addr]['offset']
                            valStr = self.cfgDict[addr]['dispFmt'] % (calVal)

                            # Update the background color based on the value
                            # If the new value is outside the normal limits, update the background color
                            # Remove the lower and upper display limits
                            lims = self.cfgDict[addr]['lims'][1:-1]
                            bgColor = self.checkLims(calVal, lims, self.colors)
                            self.statusCells[addr].setBgColor(bgColor)
                        else:
                            valStr = str(val)
                        
                        self.statusCells[addr].setVal(valStr)

    def updateCell(self, cellAddr, param, val):
        if param == "status":
            self.statusCells[cellAddr].setStatus(val)
            # self.mainWindow.statusCells[cellAddr].adjustSize()
        elif param == "bgcolor":
            self.statusCells[cellAddr].setBgColor(val)
        else:
            logging.error("Unrecognized parameter in updateCell: %s" % param)

    def checkLims(self, val, lims, colors):
        # Check where the values are relative to the limits, return the color
        idx = bisect_left(lims, val)
        return colors[idx]


class StatusCell(QFrame):
    # Empty widget with a gridlayout in it, each cell containing a label
    def __init__(self, bgcolor="gray"):
        super(StatusCell, self).__init__()

        # Gain and offset for converting to english units (ips)
        self.gain = 1
        self.offset = 0

        self.setAutoFillBackground(True)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet("QFrame { " + "background-color:" + bgcolor + ";" + "}")
        self.setContentsMargins(1, 1, 1, 1)

        # Create a gridlayout and put the appropriate labels in them
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 1, 0, 1)
        self.grid.setSpacing(0)

        # Paramater name
        self.name = QLabel("Param_Name")
        self.name.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        statusFont = self.name.font()
        statusFont.setPointSize(16)
        self.name.setFont(statusFont)
        #self.name.setStyleSheet("QLabel {border-bottom: 1px solid black; }")

        # Read the current font, modify it, and set it back
        # Matches system font
        labelFont = self.name.font()
        labelFont.setPointSize(16)
        labelFont.setBold(True)
        self.name.setFont(labelFont)

        self.value = QLabel("123.456")
        self.value.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.value.setFont(statusFont)

        self.units = QLabel("Unitless")
        self.units.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.units.setFont(statusFont)        

        # First row
        self.grid.addWidget(self.name, 0, 0)

        # Second row
        self.grid.addWidget(self.value, 1, 0)

        # Third row
        self.grid.addWidget(self.units, 2, 0)

        # Add the grid to the frame
        self.setLayout(self.grid)

    def setName(self, name):
        self.name.setText(name)

    def setVal(self, ip):
        self.value.setText(ip)

    def setUnits(self, units):
        self.units.setText(units)
    
    def setGain(self, gain):
        self.gain = gain

    def setOffset(self, offset):
        self.offset = offset

    def setBgColor(self, color:str):
        colorHex = colorName2hex(color)
        self.setStyleSheet("QFrame { " + "background-color:" + colorHex + ";" + "}")
