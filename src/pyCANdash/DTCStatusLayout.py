from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView
)


class DTCStatusLayout(QFrame):
    # Empty widget with a gridlayout in it, each cell containing a label
    def __init__(self, colCfg:dict, N_rows=10):
        super(DTCStatusLayout, self).__init__()

        self.N_rows = N_rows
        self.colCfg = colCfg

        # Create a table widget
        self.table = QTableWidget()

        # Set the number of rows and columns
        self.table.setRowCount(self.N_rows)
        self.table.setColumnCount(len(self.colCfg))
        #self.table.setStyleSheet("QTableWidget::item{padding: 8px;}")

        #Table will fit the screen horizontally 
        self.table.horizontalHeader().setStretchLastSection(True) 
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents) 
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents) 
        #self.table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.Alignment())

        # Set the default font and size
        #font = self.table.font()
        #font.setPointSize(14)
        #self.table.setFont(font)


        # Update the header 
        for colNum in range(0, len(self.colCfg)):
            self.table.setItem(0, colNum, QTableWidgetItem("   " + self.colCfg[colNum]['DisplayName'] + "   "))  
            self.table.item(0, colNum).setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)   
            #self.table.item(0, colNum).setBackground(QColor(colorName2hex('grey'))) ######
            font = self.table.item(0, colNum).font()   
            #font.setPointSize(12)                  #################
            font.setBold(True)
            self.table.item(0, colNum).setFont(font)

        self.table.horizontalHeader().hide()
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)        
        self.table.resizeColumnsToContents()

        self.table.setStyleSheet("QTableWidget::item {border-bottom: 1px solid grey; }")  #######

        # Create a gridlayout and put the appropriate labels in them
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 1, 0, 1)
        self.grid.setSpacing(0)

        # Create a grid of cells to display DTC info
        # First row
        self.grid.addWidget(self.table, 0, 0)

        # Add the grid to the frame
        self.setLayout(self.grid)

    # Update a single cell (TallStatusCell)
    def updateFromCfg(self, cfgDict, canChans):
        pass

    def updateVals(self, vals:dict):
        # vals is a dictionary containing as many entries as there are CAN interfaces
        # Each entry contains the latest data from that interface
        # Iterate over the interfaces and update the display
        for valDictKey in vals.keys():
            valDict = vals[valDictKey]

            if 'DTCs' in valDict:
                # Iterate over the DTC codes and update the display
                keys = list(valDict['DTCs'].keys())

                for rowNum in range(0, len(keys)):
                    DTC = keys[rowNum]

                    for colNum in range(0, len(self.colCfg)):
                        sigName = self.colCfg[colNum]['sigName']
                        DTCdict = valDict['DTCs'][DTC]

                        # Only display  it if it's triggered
                        if DTCdict['diag_trouble_code_triggered']:
                            
                            # Start on row 1, 0 is the header
                            # If there isn't an item, create one
                            # Row 0 is the labels so skip those
                            if self.table.item(rowNum+1 , colNum) is None:
                                self.table.setItem(rowNum+1 , colNum, QTableWidgetItem(str(DTCdict[sigName])))
                                self.table.item(rowNum+1, colNum).setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)    
                            else:
                                # Otherwise just update the value
                                self.table.item(rowNum+1 , colNum).setText(str(DTCdict[sigName]))    
                     
