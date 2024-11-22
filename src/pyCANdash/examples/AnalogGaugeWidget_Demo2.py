from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QGridLayout,
    QTabWidget,
)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

import logging
from pyCANdash.AnalogGaugeWidget import AnalogGaugeWidget
from random import random


def bound(low, high, value):
    return max(low, min(high, value))


def calc_gradiant_breaks(angles, lims):
    # Calculate the transition points for colors
    breaks = {}
    # Numbers are in absolute (0-1 is full revolution), 
    # so we need to convert to the fraction of the circle the gague takes up

    breaks["highhigh_high"] =                             (angles["span"]/360) * (lims["maxval"] - lims["highhigh"])/lims["minmaxRange"]
    breaks["high_green"]    = breaks["highhigh_high"]   + (angles["span"]/360) * (lims["highhigh"] - lims["high"])/lims["minmaxRange"]
    breaks["low_lowlow"]    = (angles["span"]/360)      - (angles["span"]/360) * (lims["lowlow"] - lims["minval"])/lims["minmaxRange"] 
    breaks["green_low"]     = breaks["low_lowlow"]      - (angles["span"]/360) * (lims["low"] - lims["lowlow"])/lims["minmaxRange"]

    for key in breaks:
        breaks[key] = bound(0, angles["span_norm"], breaks[key])

    return breaks


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
            #self.widget.setText("  " + datetime.now().strftime("%d-%b-%Y %H:%M:%S") + ": " + record.message)
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Create instances of each of the layouts
        self.mainLayout = QGridLayout()
        self.setMinimumSize(300, 300)        
        self.tabWidget = QTabWidget(self)        
        self.statusBar = StatusBar(self)

        self.tab1   =   QWidget()  
        self.tab1.setAutoFillBackground(True)     
        self.tab1.setStyleSheet("background-color: gray") 

        self.tabWidget.addTab(self.tab1, 'Overview')

        self.tab1layout = QGridLayout()

        lims = {}
        angles = {}
        lims["minval"] = 0
        lims["maxval"] = 1000
        lims["minmaxRange"] = lims["maxval"] - lims["minval"]
        # Limits must be within [minval, maxval] and be ascending. To eliminate a zone just make it 1e-3 more than the last value
        lims["lowlow"] = 100
        lims["low"] = 200
        lims["high"] = 800
        lims["highhigh"] = 900
        angles["start"] = 135
        angles["span"] = 270
        angles["span_norm"] = angles["span"]/360

        breaks = calc_gradiant_breaks(angles, lims)

        #https://khamisikibet.github.io/Docs-QT-PyQt-PySide-Custom-Widgets/docs/widgets/custom-analog-gauge
        self.gauge1 = AnalogGaugeWidget()

        # SET DEFAULT THEME        
        self.gauge1.setGaugeTheme(3)

        #self.gauge1.use_timer_event = False
        self.gauge1.setNeedleColor(255, 0, 0, 255)    
        #self.gauge1.NeedleColorReleased = self.gauge1.NeedleColor
        self.gauge1.setNeedleColorOnDrag(255, 0, 00, 255)
        
        self.gauge1.setScaleValueColor(0, 0, 0, 255)
        self.gauge1.setDisplayValueColor(0, 0, 0, 255)

        # self.gauge1 background color
        #self.gauge1.outer_circle_bg =  [
        #                [0.0, QColor("black")],
        #                [0.2, QColor("white")],
        #                [1.0, QColor("white")],
        #                ]
        
        #self.gauge1.set_CenterPointColor(0, 0, 0, 255)
        
        self.gauge1.setMinValue(lims["minval"])
        self.gauge1.setMaxValue(lims["maxval"])
        self.gauge1.value_offset = 0
        self.gauge1.valueNeedleSnapzone = 0.05

        # DEFAULT RADIUS
        self.gauge1.gauge_color_outer_radius_factor = 1
        self.gauge1.gauge_color_inner_radius_factor = 0.9
    
        # DEFAULT SCALE VALUE    
        self.gauge1.scale_angle_start_value = angles["start"]
        self.gauge1.scale_angle_size = angles["span"]
        self.gauge1.angle_offset = 0

        # Set main and minor scales
        self.gauge1.setScalaCount(10)
        self.gauge1.setScalaSubDivCount(5)
        
        # DEFAULT POLYGON COLOR    
        self.gauge1.scale_polygon_colors = [
            # 0 is full CW, rotates CCW
                        [0,                             QColor("red")],
                        [breaks["highhigh_high"],       QColor("red")],
                        [breaks["highhigh_high"] + 1e-3,QColor("yellow")],
                        [breaks["high_green"],          QColor("yellow")],
                        [breaks["high_green"] + 1e-3,   QColor("white")],
                        [breaks["green_low"],           QColor("white")],
                        [breaks["green_low"] + 1e-3,    QColor("darkYellow")],
                        [breaks["low_lowlow"],          QColor("darkYellow")],    
                        [breaks["low_lowlow"] + 1e-3,   QColor("darkRed")],                                              
                        [angles["span_norm"],           QColor("darkRed")],            
                        ]
        
        # BIG SCALE COLOR        
        self.gauge1.bigScaleMarker = QColor("black")
        
        # FINE SCALE COLOR        
        self.gauge1.fineScaleColor = QColor("black")
        
        # DEFAULT SCALE TEXT STATUS        
        self.gauge1.setEnableScaleText(True)
        self.gauge1.scale_fontname = "Orbitron"
        self.gauge1.initial_scale_fontsize = 14
        self.gauge1.scale_fontsize = self.gauge1.initial_scale_fontsize
        
        # DEFAULT VALUE TEXT STATUS        
        self.gauge1.enable_value_text = False
        self.gauge1.value_fontname = "Orbitron"
        self.gauge1.initial_value_fontsize = 40
        self.gauge1.value_fontsize = self.gauge1.initial_value_fontsize
        self.gauge1.text_radius_factor = 0.5
        
        # ENABLE BAR GRAPH BY DEFAULT        
        self.gauge1.setEnableBarGraph(True)
        
        # FILL POLYGON COLOR BY DEFAULT        
        self.gauge1.setEnableScalePolygon(True)
        
        # ENABLE CENTER POINTER BY DEFAULT        
        self.gauge1.enable_CenterPoint = True
        
        # ENABLE FINE SCALE BY DEFAULT        
        self.gauge1.enable_fine_scaled_marker = True
        
        # ENABLE BIG SCALE BY DEFAULT        
        self.gauge1.enable_big_scaled_marker = True
        
        # NEEDLE SCALE FACTOR/LENGTH        
        self.gauge1.needle_scale_factor = 0.95
        
        # ENABLE NEEDLE POLYGON BY DEFAULT        
        self.gauge1.enable_Needle_Polygon = True
        
        # ENABLE NEEDLE MOUSE TRACKING BY DEFAULT        
        self.gauge1.setMouseTracking(True)
        
        # SET self.gauge1 UNITS        
        self.gauge1.units = "℃"
        

        # Gauge 2
        self.gauge2 = AnalogGaugeWidget()
        self.gauge2.setGaugeTheme(3)  
        self.gauge2.outer_circle_bg =  [
                        [0.0, QColor("black")],
                        #[0.2, QColor("white")],
                        #[1.0, QColor("white")],
                        ] 
        self.gauge2.setScaleValueColor(255, 255, 255, 255)
        self.gauge2.setDisplayValueColor(50, 255, 255, 255)
        self.gauge2.setNeedleColor(255, 0, 0, 255)    
        self.gauge2.set_scale_polygon_colors([[0, QColor("black")]])
        # BIG SCALE COLOR        
        self.gauge2.bigScaleMarker = QColor("white")
        # FINE SCALE COLOR        
        self.gauge2.fineScaleColor = QColor("white")   
        self.gauge2.scale_polygon_colors = [
            # 0 is full CW, rotates CCW
                        [0,                             QColor("red")],
                        [breaks["highhigh_high"],       QColor("red")],
                        [breaks["highhigh_high"] + 1e-3,QColor("yellow")],
                        [breaks["high_green"],          QColor("yellow")],
                        [breaks["high_green"] + 1e-3,   QColor("black")],
                        [breaks["green_low"],           QColor("black")],
                        [breaks["green_low"] + 1e-3,    QColor("darkYellow")],
                        [breaks["low_lowlow"],          QColor("darkYellow")],    
                        [breaks["low_lowlow"] + 1e-3,   QColor("darkRed")],                                              
                        [angles["span_norm"],           QColor("darkRed")],            
                        ]        
        self.gauge2.needle_center_bg = [[0, QColor("white")], [0.5, QColor("black")], [1, QColor("white")]]   
        self.gauge2.enable_CenterPoint = False     
        self.gauge2.enable_value_text = False        

        self.gauge2.updateValue(500)

        # Gauge 3
        self.gauge3 = AnalogGaugeWidget()
        self.gauge3.setGaugeTheme(3)
        self.gauge3.scale_angle_start_value = 0
        self.gauge3.scale_angle_size = -80  
        self.gauge3.updateValue(500)       

        self.gauge4 = AnalogGaugeWidget()
        self.gauge4.setGaugeTheme(3)
        self.gauge4.scale_angle_start_value = 180
        self.gauge4.scale_angle_size = 80      
        self.gauge4.updateValue(500)   

        self.gaugeCenter = AnalogGaugeWidget()
        self.gaugeCenter.setGaugeTheme(0)
        self.gaugeCenter.updateValue(500)
     
        self.tab1layout.addWidget(self.gauge1,  0, 0, 1, 1)
        self.tab1layout.addWidget(self.gauge2, 1, 0, 1, 1)
        self.tab1layout.addWidget(self.gauge3, 0, 3, 1, 1)
        self.tab1layout.addWidget(self.gauge4, 0, 3, 1, 1)
        self.tab1layout.addWidget(self.gaugeCenter, 0, 1, 2, 2)        
        self.tab1.setLayout(self.tab1layout)



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

        # Create a timer to update the gauges
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateGauges)
        self.timer.setInterval(int(1000/60)) 
        self.timer.start()

    def updateGauges(self):
        self.gauge1.updateValue(self.newGaugeVal(self.gauge1))
        self.gauge2.updateValue(self.newGaugeVal(self.gauge2))
        self.gauge3.updateValue(self.newGaugeVal(self.gauge3))
        self.gauge4.updateValue(self.newGaugeVal(self.gauge4))
        self.gaugeCenter.updateValue(self.newGaugeVal(self.gaugeCenter))
        pass

    def newGaugeVal(self, gauge):
        rng = gauge.maxValue - gauge.minValue
        perc_range = 0.05
        adder = perc_range * rng * random() - (perc_range * rng)/2 
        newval = gauge.value + adder
        return newval

import sys
from PyQt6.QtWidgets import QApplication

def mainApp():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    mainApp()
