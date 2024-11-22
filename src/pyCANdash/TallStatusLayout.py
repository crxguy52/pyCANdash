from PyQt6 import QtCore
from bisect import bisect_left
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QGridLayout,
)

from pyCANdash.utils import colorName2hex, findUnit

class TallStatusLayout(QFrame):
    # Empty widget with a gridlayout in it, each cell containing a label
    def __init__(self, title="", bgcolor="gray"):
        super(TallStatusLayout, self).__init__()

        self.N_COLS = 2

        self.setAutoFillBackground(True)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet("QFrame { " + "background-color:" + bgcolor + ";" + "}")
        self.setContentsMargins(1, 1, 1, 1)

        # Create a gridlayout and put the appropriate labels in them
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 1, 0, 1)
        self.grid.setSpacing(0)

        self.nameLabel = QLabel(title)
        self.nameLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        self.nameLabel.setStyleSheet("QLabel {border-bottom: 1px solid black; }")
        # Read the current font, modify it, and set it back
        # Matches system font
        self.labelFont = self.nameLabel.font()
        self.labelFont.setPointSize(16)
        self.labelFont.setBold(True)
        self.nameLabel.setFont(self.labelFont)

        # First row
        self.grid.addWidget(self.nameLabel, 0, 0, 1, self.N_COLS)

        # Add the grid to the frame
        self.setLayout(self.grid)

    # Update a single cell (TallStatusCell)
    def updateFromCfg(self, cfgDict, canChans):

        self.cfgDict = cfgDict
        self.colors = cfgDict['colors']
        self.cfgDict.pop('colors')
        self.canChans = canChans

        self.statusLabels = {}
        labelCol = 0
        statusCol = 1
        unitsCol = 2

        for row in cfgDict.keys():
            rowCfg = cfgDict[row]

            if len(rowCfg['dispName']) > 0:
                name = rowCfg['dispName']
            else:
                name = rowCfg['sigName']

            if name is not None:
                label = QLabel(" " + name + ": ")
            else:
                label = QLabel("")

            font = label.font()
            font.setPointSize(14)
            font.setBold(True)
            label.setFont(font)
            label.setStyleSheet("QLabel {border-bottom: 1px solid black; }")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.grid.addWidget(label, row, labelCol)

            self.statusLabels[row] = QLabel("-")
            self.statusLabels[row].setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)            
            font.setBold(False)
            self.statusLabels[row].setFont(font)
            self.statusLabels[row].setStyleSheet("QLabel {background-color:transparent; border-bottom: 1px solid black; }")
            self.grid.addWidget(self.statusLabels[row], row, statusCol)
           
            unit, gain, offset = findUnit(rowCfg['sigName'], self.canChans, rowCfg['convert2ips'])
            self.cfgDict[row]['gain'] = gain
            self.cfgDict[row]['offset'] = offset

            unitLabel = QLabel(unit)
            unitLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)            
            font.setBold(True)
            unitLabel.setFont(font)
            unitLabel.setStyleSheet("QLabel {background-color:transparent; border-bottom: 1px solid black; }")
            self.grid.addWidget(unitLabel, row, unitsCol)


        # Add a row at the bottom that does all the stretching
        #emptyRow = len(cfgDict.keys()) + 1
        #self.grid.addWidget(QLabel(), emptyRow, 0, 1, 2)
        #self.grid.setRowStretch(emptyRow, 1)

        # Let the right column stretch
        #self.grid.setColumnStretch(1, 1)

    def updateVals(self, vals:dict):

        # vals is a dictionary containing as many entries as there are CAN interfaces
        # Each entry contains the latest data from that interface
        # Iterate over the interfaces and update the display
        for valDictKey in vals.keys():
            valDict = vals[valDictKey]

            # Iterate over all of the rows in this layout, update the display if the signal names match
            for row in self.cfgDict:
                rowCfg = self.cfgDict[row]
                sigName = rowCfg['sigName']

                if sigName in valDict:

                    val = valDict[sigName]
                    if type(val) is int or type(val) is float:
                        # if it's a number, convert it to a string
                        calVal = valDict[sigName] * self.cfgDict[row]['gain'] + self.cfgDict[row]['offset']
                        valStr = self.cfgDict[row]['dispFmt'] % (calVal)

                        # Update the background color based on the value
                        # If the new value is outside the normal limits, update the background color
                        # Remove the lower and upper display limits
                        lims = self.cfgDict[row]['lims'][1:-1]
                        bgColor = self.checkLims(calVal, lims, self.colors)
                        self.setBgColor(self.statusLabels[row], bgColor)
                    else:
                        valStr = str(val)

                    self.statusLabels[row].setText(valStr)

    def checkLims(self, val, lims, colors):
        # Check where the values are relative to the limits, return the color
        idx = bisect_left(lims, val)
        return colors[idx]

    def setBgColor(self, label:QLabel, color:str):
        colorHex = colorName2hex(color)
        label.setStyleSheet("QLabel {border-bottom: 1px solid black; background-color:" + colorHex + ";" + "}")

