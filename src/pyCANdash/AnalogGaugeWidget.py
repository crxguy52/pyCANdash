#!/usr/bin/env python

###
# Author: Stefan Holstein
# inspired by: https://github.com/Werkov/PyQt4/blob/master/examples/widgets/analogclock.py
# Thanks to https://stackoverflow.com/

# Updated by 
########################################################################
## SPINN DESIGN CODE
# YOUTUBE: (SPINN TV) https://www.youtube.com/spinnTv
# WEBSITE: spinncode.com
# GitHub : https://github.com/KhamisiKibet
# https://github.com/KhamisiKibet/QT-PyQt-PySide-Custom-Widgets/blob/main/Custom_Widgets/AnalogGaugeWidget.py
########################################################################


########################################################################
## IMPORTS
########################################################################

import os
import math

########################################################################
## MODULE UPDATED TO USE QTPY
########################################################################
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPolygon, QPolygonF, QColor, QPen, QFont, QPainter, QFontMetrics, QConicalGradient, QRadialGradient, QFontDatabase, QPixmap, QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRect, QSize, QObject, pyqtSignal


#from Custom_Widgets.Log import *
import logging
from math import isclose
from bisect import bisect_right




# AnalogGaugeWidget CLASS

class AnalogGaugeWidget(QWidget):
    """Fetches rows from a Bigtable.
    Args: 
        none
    
    """
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super(AnalogGaugeWidget, self).__init__(parent)   

        self.use_timer_event = False    # DEFAULT TIMER VALUE  
            
        self.minValue = 0               # Default min val
        self.maxValue = 1000            # Default max val
         
        self.value = self.minValue      # DEFAULT START VALUE   
        self.last_value = 0   
        
        self.value_offset = 0           # DEFAULT OFFSET   

        # DEFAULT RADIUS
        self.gauge_color_outer_radius_factor = 1
        self.gauge_color_inner_radius_factor = 0.9

        self.center_horizontal_value = 0
        self.center_vertical_value = 0
        
        # LOAD CUSTOM FONT             
        QFontDatabase.addApplicationFont(os.path.join(os.path.dirname(__file__), 'fonts/Orbitron/Orbitron-VariableFont_wght.ttf') )   
        self.pen = QPen(QColor(0, 0, 0))

        # DEFAULT SCALE VALUE    
        self.setScaleValueColor(0, 0, 0, 255)           # DEFAULT SCALE TEXT COLOR   
        self.setDisplayValueColor(0, 0, 0, 255)         # DEFAULT VALUE COLOR              
        self.scale_angle_start_value = 135
        self.scale_angle_size = 270
        self.scale_text_radius_factor = 0.8
        self.angle_offset = 0
        self.draw_360_bg = True             # Draw the background in a full circle? Otherwise stop at the end of the scale

        self.setScalaCount(10)
        self.scala_subdiv_count = 5
        self.scale_polygon_colors = []  # DEFAULT POLYGON COLOR  
        self.bigScaleMarker = QColor('black')   # BIG SCALE COLOR
        self.fineScaleColor = QColor('black')   # FINE SCALE COLOR 
        self.setEnableScalePolygon(True)    # FILL POLYGON COLOR BY DEFAULT 
        self.setEnableBarGraph(True)        # ENABLE BAR GRAPH BY DEFAULT          
        
        # DEFAULT SCALE TEXT STATUS            
        self.setEnableScaleText(True)
        self.scale_fontname = "Orbitron"
        self.initial_scale_fontsize = 14
        self.scale_fontsize = self.initial_scale_fontsize
        self.enable_fine_scaled_marker = True               # ENABLE FINE SCALE BY DEFAULT  
        self.enable_big_scaled_marker = True                # ENABLE BIG SCALE BY DEFAULT         
        
        # DEFAULT VALUE TEXT STATUS        
        self.enable_value_text = True
        self.enable_units_text = True
        self.unitAngle = None
        self.value_fontname = "Orbitron"
        self.initial_value_fontsize = 40
        self.unit_font_size = int(self.initial_value_fontsize/3)
        self.value_fontsize = self.initial_value_fontsize
        self.unit_text_radius_factor = 0.5

        # Center point
        self.set_CenterPointColor(0, 0, 0, 255)         # DEFAULT CENTER POINTER COLOR     
        self.enable_CenterPoint = True  # ENABLE CENTER POINTER BY DEFAULT     

        self.enable_Needle_Polygon = True               # ENABLE NEEDLE POLYGON BY DEFAULT
        self.setNeedleColor(0, 0, 0, 255)               # DEFAULT NEEDLE COLOR    
        self.NeedleColorReleased = self.NeedleColor     # DEFAULT NEEDLE WHEN RELEASED             
        self.setNeedleColorOnDrag(255, 0, 00, 255)      # DEFAULT NEEDLE COLOR ON DRAG       
        self.value_needle_count = 1
        self.value_needle = QObject
        self.valueNeedleSnapzone = 0.05               
        self.needle_scale_factor    = 0.8       # NEEDLE SCALE FACTOR/LENGTH    
        self.needle_back_width      = 4         # Width of needle on the non-indicating side
        self.needle_tip_width       = 2         # Width of needle at the indicating side
        self.needle_tip_prominance  = 0         # How far to stick the center of the needle out to make it pointy
        self.needle_back_length     = 30        # Distance from the center to the non-indicating extremity 
        self.setMouseTracking(True)     # ENABLE NEEDLE MOUSE TRACKING BY DEFAULT        

        self.chngBGonVal = False                # Update gauge background color based on value       

        self.otherValEn     = False             # Display other value? Speed on a tach, for example
        self.otherValAngle  = None              # Other value text position
        self.otherValRadScale = self.unit_text_radius_factor     # How far out to put the text
        self.otherValUnits  = 'abc'    
        self.otherValFontSize = self.initial_value_fontsize

             
        self.setGaugeTheme(0)    # SET DEFAULT THEME        
        self.units = "°C"        # SET GAUGE UNITS   

        # QTimer sorgt für neu Darstellung alle X ms
        # evtl performance hier verbessern mit self.update() und self.use_timer_event = False
        # todo: self.update als default ohne ueberpruefung, ob self.use_timer_event gesetzt ist oder nicht
        # Timer startet alle 10ms das event paintEvent
  
        if self.use_timer_event:
            timer = QTimer(self)
            timer.timeout.connect(self.update)
            timer.start(10)
        else:
            self.update()
       
        self.redrawBackground = True        # Redraw the background initially        
        self.rescale_method()   # RESIZE GAUGE initially


    def getPainter(self, paintOn):
        # Returns the correct painter based on what it's painting on
        if paintOn is None:
            return QPainter(self)
        else:
            return QPainter(paintOn) 
    

    # SET SCALE FONT FAMILY    
    def setScaleFontFamily(self, font):
        self.scale_fontname = str(font)
    

    # SET VALUE FONT FAMILY    
    def setValueFontFamily(self, font):
        self.value_fontname = str(font)


    # SET BIG SCALE COLOR    
    def setBigScaleColor(self, color):
        self.bigScaleMarker = QColor(color)     
    

    # SET FINE SCALE COLOR    
    def setFineScaleColor(self, color):
        self.fineScaleColor = QColor(color)   
    

    # GAUGE THEMES    
    def setGaugeTheme(self, Theme = 1):
        if Theme == 0 or Theme == None:
            self.set_scale_polygon_colors(
                                    # Starts at full CLOCKWISE and goes CCW
                                    [[.00, QColor('red')],
                                    [.1, QColor('yellow')],
                                    [.15, QColor('green')],
                                    [1, QColor('transparent')]])

            self.needle_center_bg = [
                                    [0, QColor(35, 40, 3, 255)], 
                                    [0.16, QColor(30, 36, 45, 255)], 
                                    [0.225, QColor(36, 42, 54, 255)], 
                                    [0.423963, QColor(19, 23, 29, 255)], 
                                    [0.580645, QColor(45, 53, 68, 255)], 
                                    [0.792627, QColor(59, 70, 88, 255)], 
                                    [0.935, QColor(30, 35, 45, 255)], 
                                    [1, QColor(35, 40, 3, 255)]
                                    ]

            self.outer_circle_bg =  [                                       # This is the gauge background
                                    [0.0645161, QColor(30, 35, 45, 255)], 
                                    [0.37788, QColor(57, 67, 86, 255)], 
                                    [1, QColor(30, 36, 45, 255)]
                                    ]

        if Theme == 1:
            self.set_scale_polygon_colors([[.75, QColor('red')],
                                     [.5, QColor('yellow')],
                                     [.25, QColor('green')]])

            self.needle_center_bg = [
                                    [0, QColor(35, 40, 3, 255)], 
                                    [0.16, QColor(30, 36, 45, 255)], 
                                    [0.225, QColor(36, 42, 54, 255)], 
                                    [0.423963, QColor(19, 23, 29, 255)], 
                                    [0.580645, QColor(45, 53, 68, 255)], 
                                    [0.792627, QColor(59, 70, 88, 255)], 
                                    [0.935, QColor(30, 35, 45, 255)], 
                                    [1, QColor(35, 40, 3, 255)]
                                    ]

            self.outer_circle_bg =  [
                                    [0.0645161, QColor(30, 35, 45, 255)], 
                                    [0.37788, QColor(57, 67, 86, 255)], 
                                    [1, QColor(30, 36, 45, 255)]
                                    ]

        if Theme == 2:
            self.set_scale_polygon_colors([[.25, QColor('red')],
                                     [.5, QColor('yellow')],
                                     [.75, QColor('green')]])

            self.needle_center_bg = [
                                    [0, QColor(35, 40, 3, 255)], 
                                    [0.16, QColor(30, 36, 45, 255)], 
                                    [0.225, QColor(36, 42, 54, 255)], 
                                    [0.423963, QColor(19, 23, 29, 255)], 
                                    [0.580645, QColor(45, 53, 68, 255)], 
                                    [0.792627, QColor(59, 70, 88, 255)], 
                                    [0.935, QColor(30, 35, 45, 255)], 
                                    [1, QColor(35, 40, 3, 255)]
                                    ]

            self.outer_circle_bg =  [
                                    [0.0645161, QColor(30, 35, 45, 255)], 
                                    [0.37788, QColor(57, 67, 86, 255)], 
                                    [1, QColor(30, 36, 45, 255)]
                                    ]

        elif Theme == 3:
            self.set_scale_polygon_colors([[.00, QColor('white')]])

            self.needle_center_bg = [
                                    [0, QColor('white')], 
                                    ]

            self.outer_circle_bg =  [
                                    [0, QColor('white')], 
                                    ]

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 4:
            self.set_scale_polygon_colors([[1, QColor('black')]])

            self.needle_center_bg = [
                                    [0, QColor('black')], 
                                    ]

            self.outer_circle_bg =  [
                                    [0, QColor('black')], 
                                    ]

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 5:
            self.set_scale_polygon_colors([[1, QColor("#029CDE")]])  

            self.needle_center_bg = [
                                    [0, QColor("#029CDE")], 
                                    ]

            self.outer_circle_bg =  [
                                    [0, QColor("#029CDE")], 
                                    ]

        elif Theme == 6:
            self.set_scale_polygon_colors([[.75, QColor("#01ADEF")],
                                     [.5, QColor("#0086BF")],
                                     [.25, QColor("#005275")]])

            self.needle_center_bg = [
                                    [0, QColor(0, 46, 61, 255)], 
                                    [0.322581, QColor(1, 173, 239, 255)], 
                                    [0.571429, QColor(0, 73, 99, 255)],
                                    [1, QColor(0, 46, 61, 255)]
                                    ]

            self.outer_circle_bg =  [
                                    [0.0645161, QColor(0, 85, 116, 255)], 
                                    [0.37788, QColor(1, 173, 239, 255)], 
                                    [1, QColor(0, 69, 94, 255)]
                                    ]

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 7:
            self.set_scale_polygon_colors([[.25, QColor("#01ADEF")],
                                     [.5, QColor("#0086BF")],
                                     [.75, QColor("#005275")]])

            self.needle_center_bg = [
                                    [0, QColor(0, 46, 61, 255)], 
                                    [0.322581, QColor(1, 173, 239, 255)], 
                                    [0.571429, QColor(0, 73, 99, 255)],
                                    [1, QColor(0, 46, 61, 255)]
                                    ]

            self.outer_circle_bg =  [
                                    [0.0645161, QColor(0, 85, 116, 255)], 
                                    [0.37788, QColor(1, 173, 239, 255)], 
                                    [1, QColor(0, 69, 94, 255)]
                                    ]

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 8:
            self.setCustomGaugeTheme(
                color1 = "#ffaa00",
                color2= "#7d5300",
                color3 = "#3e2900"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 9:
            self.setCustomGaugeTheme(
                color1 = "#3e2900",
                color2= "#7d5300",
                color3 = "#ffaa00"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 10:
            self.setCustomGaugeTheme(
                color1 = "#ff007f",
                color2= "#aa0055",
                color3 = "#830042"
            )


            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 11:
            self.setCustomGaugeTheme(
                color1 = "#830042",
                color2= "#aa0055",
                color3 = "#ff007f"
            )
            
            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 12:
            self.setCustomGaugeTheme(
                color1 = "#ffe75d",
                color2= "#896c1a",
                color3 = "#232803"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 13:
            self.setCustomGaugeTheme(
                color1 = "#ffe75d",
                color2= "#896c1a",
                color3 = "#232803"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 14:
            self.setCustomGaugeTheme(
                color1 = "#232803",
                color2= "#821600",
                color3 = "#ffe75d"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 15:
            self.setCustomGaugeTheme(
                color1 = "#00FF11",
                color2= "#00990A",
                color3 = "#002603"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 16:
            self.setCustomGaugeTheme(
                color1 = "#002603",
                color2= "#00990A",
                color3 = "#00FF11"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 17:
            self.setCustomGaugeTheme(
                color1 = "#00FFCC",
                color2= "#00876C",
                color3 = "#00211B"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 18:
            self.setCustomGaugeTheme(
                color1 = "#00211B",
                color2= "#00876C",
                color3 = "#00FFCC"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 19:
            self.setCustomGaugeTheme(
                color1 = "#001EFF",
                color2= "#001299",
                color3 = "#000426"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 20:
            self.setCustomGaugeTheme(
                color1 = "#000426",
                color2= "#001299",
                color3 = "#001EFF"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 21:
            self.setCustomGaugeTheme(
                color1 = "#F200FF",
                color2= "#85008C",
                color3 = "#240026"
            )

            self.bigScaleMarker = QColor('black')
            self.fineScaleColor = QColor('black')

        elif Theme == 22:
            self.setCustomGaugeTheme(
                color1 = "#240026",
                color2= "#85008C",
                color3 = "#F200FF"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 23:
            self.setCustomGaugeTheme(
                color1 = "#FF0022",
                color2= "#080001",
                color3 = "#009991"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')

        elif Theme == 24:
            self.setCustomGaugeTheme(
                color1 = "#009991",
                color2= "#080001",
                color3 = "#FF0022"
            )

            self.bigScaleMarker = QColor('white')
            self.fineScaleColor = QColor('white')
        
        elif Theme == 25:
            self.outer_circle_bg =  [
                    [0.0, QColor('black')],
                    #[0.2, QColor('white],
                    #[1.0, QColor('white],
                    ] 
            self.setScaleValueColor(255, 255, 255, 255)
            self.setDisplayValueColor(255, 255, 255, 255)
            self.setNeedleColor(255, 0, 0, 255)    
            self.set_scale_polygon_colors([[0, QColor('black')]])                 
            self.bigScaleMarker         = QColor('white')  # BIG SCALE COLOR         
            self.fineScaleColor         = QColor('white')  # FINE SCALE COLOR  
            self.chngBGonVal            = True      # Update gauge background color based on value 

            self.needle_center_bg = [[0, QColor('white')], [0.5, QColor('black')], [1, QColor('white')]]   
            self.enable_CenterPoint = False     
            self.enable_value_text = False                      


    # SET CUSTOM GAUGE THEME    
    def setCustomGaugeTheme(self, **colors):
        if "color1" in colors and len(str(colors['color1'])) > 0:
            if "color2" in colors and len(str(colors['color2'])) > 0:
                if "color3" in colors and len(str(colors['color3'])) > 0:

                    self.set_scale_polygon_colors([[.25, QColor(str(colors['color1']))],
                                            [.5, QColor(str(colors['color2']))],
                                            [.75, QColor(str(colors['color3']))]])

                    self.needle_center_bg = [
                                            [0, QColor(str(colors['color3']))], 
                                            [0.322581, QColor(str(colors['color1']))], 
                                            [0.571429, QColor(str(colors['color2']))],
                                            [1, QColor(str(colors['color3']))]
                                            ]

                    self.outer_circle_bg =  [
                                            [0.0645161, QColor(str(colors['color3']))], 
                                            [0.36, QColor(str(colors['color1']))], 
                                            [1, QColor(str(colors['color2']))]
                                            ]

                else:

                    self.set_scale_polygon_colors([[.5, QColor(str(colors['color1']))],
                                             [1, QColor(str(colors['color2']))]])

                    self.needle_center_bg = [
                                            [0, QColor(str(colors['color2']))], 
                                            [1, QColor(str(colors['color1']))]
                                            ]

                    self.outer_circle_bg =  [
                                            [0, QColor(str(colors['color2']))], 
                                            [1, QColor(str(colors['color2']))]
                                            ]

            else:

                self.set_scale_polygon_colors([[1, QColor(str(colors['color1']))]])

                self.needle_center_bg = [
                                        [1, QColor(str(colors['color1']))]
                                        ]

                self.outer_circle_bg =  [
                                        [1, QColor(str(colors['color1']))]
                                        ]

        else:
            self.setGaugeTheme(0)
            logging.info(self, "Custom Gauge Theme: color1 is not defined")


    # SET SCALE POLYGON COLOR    
    def setScalePolygonColor(self, **colors):
        if "color1" in colors and len(str(colors['color1'])) > 0:
            if "color2" in colors and len(str(colors['color2'])) > 0:
                if "color3" in colors and len(str(colors['color3'])) > 0:

                    self.set_scale_polygon_colors([[.25, QColor(str(colors['color1']))],
                                            [.5, QColor(str(colors['color2']))],
                                            [.75, QColor(str(colors['color3']))]])

                else:

                    self.set_scale_polygon_colors([[.5, QColor(str(colors['color1']))],
                                             [1, QColor(str(colors['color2']))]])

            else:

                self.set_scale_polygon_colors([[1, QColor(str(colors['color1']))]])

        else:
            logging.info(self, "Custom Gauge Theme: color1 is not defined")

    
    # SET NEEDLE CENTER COLOR    
    def setNeedleCenterColor(self, **colors):
        if "color1" in colors and len(str(colors['color1'])) > 0:
            if "color2" in colors and len(str(colors['color2'])) > 0:
                if "color3" in colors and len(str(colors['color3'])) > 0:

                    self.needle_center_bg = [
                                            [0, QColor(str(colors['color3']))], 
                                            [0.322581, QColor(str(colors['color1']))], 
                                            [0.571429, QColor(str(colors['color2']))],
                                            [1, QColor(str(colors['color3']))]
                                            ]

                else:

                    self.needle_center_bg = [
                                            [0, QColor(str(colors['color2']))], 
                                            [1, QColor(str(colors['color1']))]
                                            ]

            else:

                self.needle_center_bg = [
                                        [1, QColor(str(colors['color1']))]
                                        ]
        else:
            logging.info(self, "Custom Gauge Theme: color1 is not defined")

    
    # SET OUTER CIRCLE COLOR
    def setOuterCircleColor(self, **colors):
        if "color1" in colors and len(str(colors['color1'])) > 0:
            if "color2" in colors and len(str(colors['color2'])) > 0:
                if "color3" in colors and len(str(colors['color3'])) > 0:

                    self.outer_circle_bg =  [
                                            [0.0645161, QColor(str(colors['color3']))], 
                                            [0.37788, QColor(str(colors['color1']))], 
                                            [1, QColor(str(colors['color2']))]
                                            ]

                else:

                    self.outer_circle_bg =  [
                                            [0, QColor(str(colors['color2']))], 
                                            [1, QColor(str(colors['color2']))]
                                            ]

            else:

                self.outer_circle_bg =  [
                                        [1, QColor(str(colors['color1']))]
                                        ]

        else:
            logging.info(self, "Custom Gauge Theme: color1 is not defined")


    # RESCALE    
    def rescale_method(self):
        
        # SET WIDTH AND HEIGHT
        
        if self.width() <= self.height():
            self.widget_diameter = self.width()
        else:
            self.widget_diameter = self.height()

        
        # SET NEEDLE SIZE        
        self.change_value_needle_style([QPolygon([
            QPoint(self.needle_back_width, self.needle_back_length),
            QPoint(-self.needle_back_width, self.needle_back_length),
            QPoint(-self.needle_tip_width, - int(self.widget_diameter / 2 * self.needle_scale_factor)),
            QPoint(0, - int(self.widget_diameter / 2 * self.needle_scale_factor + 0) - self.needle_tip_prominance),
            QPoint(self.needle_tip_width, - int(self.widget_diameter / 2 * self.needle_scale_factor))
        ])])
        
        # SET FONT SIZE        
        self.scale_fontsize = int(self.initial_scale_fontsize * self.widget_diameter / 400)
        self.value_fontsize = int(self.initial_value_fontsize * self.widget_diameter / 400)

        # Set flag to redraw the background
        self.redrawBackground = True


    def change_value_needle_style(self, design):
        # prepared for multiple needle instrument
        self.value_needle = []
        for i in design:
            self.value_needle.append(i)
        if not self.use_timer_event:
            self.update()

    
    # UPDATE VALUE    
    def updateValue(self, value, mouse_controlled = False):
        # if not mouse_controlled:
        #     self.value = value
        #
        # if mouse_controlled:
        #     self.valueChanged.emit(int(value))

        if value <= self.minValue:
            self.value = self.minValue
        elif value >= self.maxValue:
            self.value = self.maxValue
        else:
            self.value = value

        # If we've defined limits, change the background color 
        if hasattr(self, 'lims') and self.chngBGonVal is True:    
            if not self.outer_circle_bg[0][1] == self.checkLims(self.value):
                self.outer_circle_bg =  [
                        [0.0, self.checkLims(self.value)],
                        ]
                self.redrawBackground = True
            
        # self.paintEvent("")
        self.valueChanged.emit(int(value))

        # ohne timer: aktiviere self.update()
        if not self.use_timer_event:
            self.update()


    def updateOtherValue(self, value):

        self.otherValue = value
        self.valueChanged.emit(int(value))

        # ohne timer: aktiviere self.update()
        if not self.use_timer_event:
            self.update()            


    def updateAngleOffset(self, offset):
        self.angle_offset = offset
        if not self.use_timer_event:
            self.update()


    def center_horizontal(self, value):
        self.center_horizontal_value = value


    def center_vertical(self, value):
        self.center_vertical_value = value

    
    # SET NEEDLE COLOR    
    def setNeedleColor(self, R=50, G=50, B=50, Transparency=255):
        # Red: R = 0 - 255
        # Green: G = 0 - 255
        # Blue: B = 0 - 255
        # Transparency = 0 - 255
        self.NeedleColor = QColor(R, G, B, Transparency)
        self.NeedleColorReleased = self.NeedleColor

        if not self.use_timer_event:
            self.update()
    
    
    # SET NEEDLE COLOR ON DRAG    
    def setNeedleColorOnDrag(self, R=50, G=50, B=50, Transparency=255):
        # Red: R = 0 - 255
        # Green: G = 0 - 255
        # Blue: B = 0 - 255
        # Transparency = 0 - 255
        self.NeedleColorDrag = QColor(R, G, B, Transparency)

        if not self.use_timer_event:
            self.update()

    
    # SET SCALE VALUE COLOR    
    def setScaleValueColor(self, R=50, G=50, B=50, Transparency=255):
        # Red: R = 0 - 255
        # Green: G = 0 - 255
        # Blue: B = 0 - 255
        # Transparency = 0 - 255
        self.ScaleValueColor = QColor(R, G, B, Transparency)

        if not self.use_timer_event:
            self.update()

    
    # SET DISPLAY VALUE COLOR    
    def setDisplayValueColor(self, R=50, G=50, B=50, Transparency=255):
        # Red: R = 0 - 255
        # Green: G = 0 - 255
        # Blue: B = 0 - 255
        # Transparency = 0 - 255
        self.DisplayValueColor = QColor(R, G, B, Transparency)

        if not self.use_timer_event:
            self.update()

    
    # SET CENTER POINTER COLOR - this is unused!    
    def set_CenterPointColor(self, R=50, G=50, B=50, Transparency=255):
        self.CenterPointColor = QColor(R, G, B, Transparency)

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE NEEDLE POLYGON    
    def setEnableNeedlePolygon(self, enable = True):
        self.enable_Needle_Polygon = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE SCALE TEXT    
    def setEnableScaleText(self, enable = True):
        self.enable_scale_text = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE BAR GRAPH    
    def setEnableBarGraph(self, enable = True):
        self.enableBarGraph = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE VALUE TEXT    
    def setEnableValueText(self, enable = True):
        self.enable_value_text = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE CENTER POINTER    
    def setEnableCenterPoint(self, enable = True):
        self.enable_CenterPoint = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE FILLED POLYGON    
    def setEnableScalePolygon(self, enable = True):
        self.enable_filled_Polygon = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE BIG SCALE    
    def setEnableBigScaleGrid(self, enable = True):
        self.enable_big_scaled_marker = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE FINE SCALE    
    def setEnableFineScaleGrid(self, enable = True):
        self.enable_fine_scaled_marker = enable

        if not self.use_timer_event:
            self.update()

    
    # SHOW HIDE SCALA MAIN CONT    
    def setScalaCount(self, count):
        if count < 1:
            count = 1
        self.scalaCount = count

        if not self.use_timer_event:
            self.update()


    # Set Subdivisions   
    def setScalaSubDivCount(self, count):
        if count < 1:
            count = 1
        self.scala_subdiv_count = count

        if not self.use_timer_event:
            self.update()            

    
    # SET MINIMUM VALUE    
    def setMinValue(self, min):
        if self.value < min:
            self.value = min
        if min >= self.maxValue:
            self.minValue = self.maxValue - 1
        else:
            self.minValue = min

        if not self.use_timer_event:
            self.update()

    
    # SET MAXIMUM VALUE    
    def setMaxValue(self, max):
        if self.value > max:
            self.value = max
        if max <= self.minValue:
            self.maxValue = self.minValue + 1
        else:
            self.maxValue = max

        if not self.use_timer_event:
            self.update()

    
    # SET SCALE ANGLE    
    def setScaleStartAngle(self, value):
        # Value range in DEG: 0 - 360
        self.scale_angle_start_value = value

        if not self.use_timer_event:
            self.update()

    
    # SET SCALE SIZE    
    def setTotalScaleAngleSize(self, value):
        self.scale_angle_size = value

        if not self.use_timer_event:
            self.update()

    
    # SET GAUGE COLOR OUTER RADIUS    
    def setGaugeColorOuterRadiusFactor(self, value):
        self.gauge_color_outer_radius_factor = float(value) / 1000

        if not self.use_timer_event:
            self.update()

    
    # SET GAUGE COLOR INNER RADIUS    
    def setGaugeColorInnerRadiusFactor(self, value):
        self.gauge_color_inner_radius_factor = float(value) / 1000

        if not self.use_timer_event:
            self.update()

    
    # SET SCALE POLYGON COLOR    
    def set_scale_polygon_colors(self, color_array):
        if 'list' in str(type(color_array)):
            self.scale_polygon_colors = color_array
        elif color_array == None:
            self.scale_polygon_colors = [[.0, QColor('transparent')]]
        else:
            self.scale_polygon_colors = [[.0, QColor('transparent')]]

        if not self.use_timer_event:
            self.update()

    
    # GET MAXIMUM VALUE    
    def get_value_max(self):
        return self.maxValue

    ###############################################################################################
    # SCALE PAINTER
    ###############################################################################################

    
    # CREATE PIE    
    def create_polygon_pie(self, outer_radius, inner_raduis, start, lenght, bar_graph = True):
        polygon_pie = QPolygonF()
        # start = self.scale_angle_start_value
        # start = 0
        # lenght = self.scale_angle_size
        # lenght = 180
        # inner_raduis = self.width()/4
        n = 360     # angle steps size for full circle
        # changing n value will causes drawing issues
        w = 360 / n   # angle per step
        # create outer circle line from "start"-angle to "start + lenght"-angle
        x = 0
        y = 0

        # todo enable/disable bar graf here
        if not self.enableBarGraph and bar_graph:
            # float_value = ((lenght / (self.maxValue - self.minValue)) * (self.value - self.minValue))
            lenght = int(round((lenght / (self.maxValue - self.minValue)) * (self.value - self.minValue)))

        for i in range(lenght+1):                                              # add the points of polygon
            t = w * i + start - self.angle_offset
            x = int(outer_radius * math.cos(math.radians(t)))
            y = int(outer_radius * math.sin(math.radians(t)))
            polygon_pie.append(QPointF(x, y))
        # create inner circle line from "start + lenght"-angle to "start"-angle
        for i in range(lenght+1):                                              # add the points of polygon
            t = w * (lenght - i) + start - self.angle_offset
            x = int(inner_raduis * math.cos(math.radians(t)))
            y = int(inner_raduis * math.sin(math.radians(t)))
            polygon_pie.append(QPointF(x, y))

        # close outer line
        polygon_pie.append(QPointF(x, y))
        return polygon_pie


    def draw_filled_polygon(self, outline_pen_with=0, paintOn=None):
        if not self.scale_polygon_colors == None:
                
            painter_filled_polygon = self.getPainter(paintOn)
            painter_filled_polygon.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Koordinatenursprung in die Mitte der Flaeche legen
            painter_filled_polygon.translate(self.width() / 2, self.height() / 2)

            painter_filled_polygon.setPen(Qt.PenStyle.NoPen)

            self.pen.setWidth(outline_pen_with)
            if outline_pen_with > 0:
                painter_filled_polygon.setPen(self.pen)

            colored_scale_polygon = self.create_polygon_pie(
                ((self.widget_diameter / 2) - (self.pen.width() / 2)) * self.gauge_color_outer_radius_factor,
                (((self.widget_diameter / 2) - (self.pen.width() / 2)) * self.gauge_color_inner_radius_factor),
                self.scale_angle_start_value, self.scale_angle_size)

            gauge_rect = QRect(QPoint(0, 0), QSize(int(self.widget_diameter / 2 - 1), int(self.widget_diameter - 1)))
            grad = QConicalGradient(QPointF(0, 0), - self.scale_angle_size - self.scale_angle_start_value +
                                    self.angle_offset - 1)

            # todo definition scale color as array here
            for eachcolor in self.scale_polygon_colors:
                grad.setColorAt(eachcolor[0], eachcolor[1])
            # grad.setColorAt(.00, QColor('red)
            # grad.setColorAt(.1, QColor('yellow)
            # grad.setColorAt(.15, QColor('green)
            # grad.setColorAt(1, QColor('transparent'))
            # self.brush = QBrush(QColor(255, 0, 255, 255))
            # grad.setStyle(QColor.Dense6Pattern)
            # painter_filled_polygon.setBrush(self.brush)
            painter_filled_polygon.setBrush(grad)
           

            painter_filled_polygon.drawPolygon(colored_scale_polygon)
            # return painter_filled_polygon


    def draw_icon_image(self):
        pass

    ###############################################################################################
    # BIG SCALE MARKERS
    ###############################################################################################
    def draw_big_scaled_marker(self, paintOn=None):
        my_painter = self.getPainter(paintOn)
        my_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Koordinatenursprung in die Mitte der Flaeche legen
        my_painter.translate(self.width() / 2, self.height() / 2)

        # my_painter.setPen(Qt.PenStyle.NoPen)
        self.pen = QPen(self.bigScaleMarker)
        self.pen.setWidth(2)
        # # if outline_pen_with > 0:
        my_painter.setPen(self.pen)

        my_painter.rotate(self.scale_angle_start_value - self.angle_offset)
        steps_size = (float(self.scale_angle_size) / float(self.scalaCount))
        scale_line_outer_start = int(self.widget_diameter/2)
        scale_line_lenght = int((self.widget_diameter / 2) - (self.widget_diameter / 20))
        for i in range(self.scalaCount+1):
            my_painter.drawLine(scale_line_lenght, 0, scale_line_outer_start, 0)
            my_painter.rotate(steps_size)


    def create_scale_marker_values_text(self, paintOn=None):
        painter = self.getPainter(paintOn)
        # painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Koordinatenursprung in die Mitte der Flaeche legen
        painter.translate(self.width() / 2, self.height() / 2)
        # painter.save()
        font = QFont(self.scale_fontname, pointSize=int(self.scale_fontsize))
        fm = QFontMetrics(font)

        pen_shadow = QPen()

        pen_shadow.setBrush(self.ScaleValueColor)
        painter.setPen(pen_shadow)

        text_radius = self.widget_diameter/2 * self.scale_text_radius_factor

        scale_per_div = int((self.maxValue - self.minValue) / self.scalaCount)

        angle_distance = (float(self.scale_angle_size) / float(self.scalaCount))
        for i in range(self.scalaCount + 1):
            # text = str(int((self.maxValue - self.minValue) / self.scalaCount * i))
            text = str(int(self.minValue + scale_per_div * i))
            w = fm.horizontalAdvance(text) + 1
            h = fm.height()
            painter.setFont(QFont(self.scale_fontname, pointSize=int(self.scale_fontsize)))
            angle = angle_distance * i + float(self.scale_angle_start_value - self.angle_offset)
            x = int(text_radius * math.cos(math.radians(angle)))
            y = int(text_radius * math.sin(math.radians(angle)))

            text = [x - int(w/2), y - int(h/2), int(w), int(h), Qt.AlignmentFlag.AlignCenter, text]
            painter.drawText(text[0], text[1], text[2], text[3], text[4], text[5])
        # painter.restore()

    
    # FINE SCALE MARKERS
    def create_fine_scaled_marker(self, paintOn=None):
        #  Description_dict = 0
        my_painter = self.getPainter(paintOn)

        my_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Koordinatenursprung in die Mitte der Flaeche legen
        my_painter.translate(self.width() / 2, self.height() / 2)

        my_painter.setPen(self.fineScaleColor)
        my_painter.rotate(self.scale_angle_start_value - self.angle_offset)
        steps_size = (float(self.scale_angle_size) / float(self.scalaCount * self.scala_subdiv_count))
        scale_line_outer_start = int(self.widget_diameter/2)
        scale_line_lenght = int((self.widget_diameter / 2) - (self.widget_diameter / 40))
        for i in range((self.scalaCount * self.scala_subdiv_count)+1):
            my_painter.drawLine(scale_line_lenght, 0, scale_line_outer_start, 0)
            my_painter.rotate(steps_size)

    
    # VALUE TEXT    
    def create_values_text(self, paintOn=None):
        painter = self.getPainter(paintOn)
        try:
            painter.setRenderHint(QPainter.HighQualityAntialiasing)
        except AttributeError:
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            except AttributeError:
                # Neither hint is available; you can handle this case as needed
                pass

        # painter.setRenderHint(QPainter.AA_HighDpiScaling)
        # painter.setRenderHint(QPainter.SmoothPixmapTransform)

        painter.translate(self.width() / 2, self.height() / 2)
        # painter.save()
        # xShadow = 3.0
        # yShadow = 3.0
        font = QFont(self.value_fontname, int(self.value_fontsize))
        font.setBold(True)
        fm = QFontMetrics(font)

        pen_shadow = QPen()

        pen_shadow.setBrush(self.DisplayValueColor)
        painter.setPen(pen_shadow)

        text_radius = self.widget_diameter / 2 * self.unit_text_radius_factor

        # angle_distance = (float(self.scale_angle_size) / float(self.scalaCount))
        # for i in range(self.scalaCount + 1):
        text = str(int(self.value))
        w = fm.horizontalAdvance(text) + 1
        h = fm.height()
        painter.setFont(font)

        # Mitte zwischen Skalenstart und Skalenende:
        # Skalenende = Skalenanfang - 360 + Skalenlaenge
        # Skalenmitte = (Skalenende - Skalenanfang) / 2 + Skalenanfang
        angle_end = float(self.scale_angle_start_value + self.scale_angle_size - 360)
        angle = (angle_end - self.scale_angle_start_value) / 2 + self.scale_angle_start_value

        x = int(text_radius * math.cos(math.radians(angle)))
        y = int(text_radius * math.sin(math.radians(angle)))
        text = [x - int(w/2), y - int(h/2), int(w), int(h), Qt.AlignmentFlag.AlignCenter, text]
        painter.drawText(text[0], text[1], text[2], text[3], text[4], text[5])

    
    # UNITS TEXT    
    def create_units_text(self, paintOn=None):
        painter = self.getPainter(paintOn)
        try:
            painter.setRenderHint(QPainter.HighQualityAntialiasing)
        except AttributeError:
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            except AttributeError:
                # Neither hint is available; you can handle this case as needed
                pass


        painter.translate(self.width() / 2, self.height() / 2)
        font = QFont(self.value_fontname, self.unit_font_size)
        font.setBold(True)
        fm = QFontMetrics(font)

        pen_shadow = QPen()

        pen_shadow.setBrush(self.DisplayValueColor)
        painter.setPen(pen_shadow)

        text_radius = self.widget_diameter / 2 * self.unit_text_radius_factor

        text = str(self.units)
        w = fm.horizontalAdvance(text) + 1
        h = fm.height()*(text.count('\n') + 1)
        painter.setFont(font)
      
        if self.unitAngle is not None:
            angle = self.unitAngle
        else:
            angle_end = float(self.scale_angle_start_value + self.scale_angle_size + 180)
            angle = (angle_end - self.scale_angle_start_value) / 2 + self.scale_angle_start_value

        x = int(text_radius * math.cos(math.radians(angle)))
        y = int(text_radius * math.sin(math.radians(angle)))
        text = [x - int(w/2), y - int(h/2), int(w), int(h), Qt.AlignmentFlag.AlignCenter, text]
        painter.drawText(text[0], text[1], text[2], text[3], text[4], text[5])


    # UNITS TEXT    
    def create_otherVar_text(self, paintOn=None):
        painter = self.getPainter(paintOn)
        try:
            painter.setRenderHint(QPainter.HighQualityAntialiasing)
        except AttributeError:
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            except AttributeError:
                # Neither hint is available; you can handle this case as needed
                pass

        # Move to the center of the gauge
        painter.translate(self.width() / 2, self.height() / 2)
        font = QFont(self.value_fontname, int(self.otherValFontSize / 2.5))
        font.setBold(True)
        fm = QFontMetrics(font)

        pen_shadow = QPen()

        pen_shadow.setBrush(self.DisplayValueColor)
        painter.setPen(pen_shadow)

        text_radius = self.widget_diameter / 2 * self.otherValRadScale

        text = f"{float(self.otherValue):0.0f}\n{self.otherValUnits.upper()}"

        # Calculate a constant width - 3 digits
        # Otherwise it shimmys side to side bc ' ' is not same size as 0
        sizeText = f"{float(self.otherValue):03.0f}\n{self.otherValUnits.upper()}"

        w = fm.horizontalAdvance(sizeText) + 1
        h = fm.height()*2
        painter.setFont(font)
      
        if self.otherValAngle is not None:
            angle = self.otherValAngle
        else:
            angle_end = float(self.scale_angle_start_value + self.scale_angle_size)
            angle = (angle_end - self.scale_angle_start_value) / 2 + self.scale_angle_start_value

        x = int(text_radius * math.cos(math.radians(angle)))
        y = int(text_radius * math.sin(math.radians(angle)))
        text = [x - int(w/2), y - int(h/2), int(w), int(h), Qt.AlignmentFlag.AlignRight, text]
        painter.drawText(text[0], text[1], text[2], text[3], text[4], text[5])
    
    # CENTER POINTER    
    def draw_big_needle_center_point(self, diameter=30, paintOn=None):
        painter = self.getPainter(paintOn)
        # painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Koordinatenursprung in die Mitte der Flaeche legen
        painter.translate(self.width() / 2, self.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        # painter.setPen(Qt.PenStyle.NoPen)

        # painter.setBrush(self.CenterPointColor)
        # diameter = diameter # self.widget_diameter/6
        # painter.drawEllipse(int(-diameter / 2), int(-diameter / 2), int(diameter), int(diameter))


        # create_polygon_pie(self, outer_radius, inner_raduis, start, lenght)
        colored_scale_polygon = self.create_polygon_pie(
                ((self.widget_diameter / 8) - (self.pen.width() / 2)),
                0,
                self.scale_angle_start_value, 360, False)

        # 150.0 0.0 131 360

        grad = QConicalGradient(QPointF(0, 0), 0)

        # todo definition scale color as array here
        for eachcolor in self.needle_center_bg:
            grad.setColorAt(eachcolor[0], eachcolor[1])
        # grad.setColorAt(.00, QColor('red)
        # grad.setColorAt(.1, QColor('yellow)
        # grad.setColorAt(.15, QColor('green)
        # grad.setColorAt(1, QColor('transparent'))
        painter.setBrush(grad)
        # self.brush = QBrush(QColor(255, 0, 255, 255))
        # painter_filled_polygon.setBrush(self.brush)

        painter.drawPolygon(colored_scale_polygon)
        # return painter_filled_polygon

    
    # CREATE OUTER COVER    
    def draw_outer_circle(self, diameter=30, paintOn=None):

        painter = self.getPainter(paintOn)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.translate(self.width() / 2, self.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)

        if self.draw_360_bg:
            end_angle = 360
        else:
            end_angle = self.scale_angle_size

        colored_scale_polygon = self.create_polygon_pie(
                ((self.widget_diameter / 2) - (self.pen.width())),
                (0),
                self.scale_angle_start_value, end_angle, False)

        radialGradient = QRadialGradient(QPointF(0, 0), self.width())

        for eachcolor in self.outer_circle_bg:
            radialGradient.setColorAt(eachcolor[0], eachcolor[1])


        painter.setBrush(radialGradient)

        painter.drawPolygon(colored_scale_polygon)

    
    # NEEDLE POINTER    
    def draw_needle(self, paintOn=None):
        
        painter = self.getPainter(paintOn)

        # painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Koordinatenursprung in die Mitte der Flaeche legen
        painter.translate(self.width() / 2, self.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.NeedleColor)
        painter.rotate(((self.value - self.value_offset - self.minValue) * self.scale_angle_size /
                        (self.maxValue - self.minValue)) + 90 + self.scale_angle_start_value)

        painter.drawConvexPolygon(self.value_needle[0])

    ###############################################################################################
    # EVENTS
    ###############################################################################################

    
    # ON WINDOW RESIZE    
    def resizeEvent(self, event):
        # self.resized.emit()
        # return super(self.parent, self).resizeEvent(event)
        self.rescale_method()
        # self.emit(QtCore.pyqtSignal("resize()"))

    
    # ON PAINT EVENT
    def paintEvent(self, event):
        # Main Drawing Event:
        # Will be executed on every change
        # vgl http://doc.qt.io/qt-4.8/qt-demos-affine-xform-cpp.html

        if self.redrawBackground is True:
            self.bgPixMap = QPixmap(self.width(), self.height())
            self.bgPixMap.fill(QColor('transparent'))

            self.draw_outer_circle(paintOn=self.bgPixMap)
            #self.draw_icon_image(paintOn=self.bgPixMap)
            
            # colored pie area
            if self.enable_filled_Polygon:
                self.draw_filled_polygon(paintOn=self.bgPixMap)

            # draw scale marker lines
            if self.enable_fine_scaled_marker:
                self.create_fine_scaled_marker(paintOn=self.bgPixMap)
            if self.enable_big_scaled_marker:
                self.draw_big_scaled_marker(paintOn=self.bgPixMap)

            # draw scale marker value text
            if self.enable_scale_text:
                self.create_scale_marker_values_text(paintOn=self.bgPixMap)

            if self.enable_units_text:
                self.create_units_text(paintOn=self.bgPixMap)

            self.redrawBackground = False

        # Draw the pixmap
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.bgPixMap)
        painter.end()

        # draw needle 1
        if self.enable_Needle_Polygon:
            # Always redraw this
            self.draw_needle()

        # Display Value
        if self.enable_value_text:
            self.create_values_text() 

        # If we've enabled the other value, paint that
        if self.otherValEn:
            self.create_otherVar_text()           

        ## Draw Center Point
        if self.enable_CenterPoint:
            # Always redraw this
            self.draw_big_needle_center_point(diameter=(self.widget_diameter / 6))


    ###############################################################################################
    # MOUSE EVENTS
    ###############################################################################################

    def setMouseTracking(self, flag):
        def recursive_set(parent):
            for child in parent.findChildren(QObject):
                try:
                    child.setMouseTracking(flag)
                except:
                    pass
                recursive_set(child)

        QWidget.setMouseTracking(self, flag)
        recursive_set(self)


    def mouseReleaseEvent(self, QMouseEvent):
        self.NeedleColor = self.NeedleColorReleased

        if not self.use_timer_event:
            self.update()
        pass

    ########################################################################
    ## MOUSE LEAVE EVENT
    ########################################################################
    def leaveEvent(self, event):
        self.NeedleColor = self.NeedleColorReleased
        self.update() 


    def mouseMoveEvent(self, event:QMouseEvent):
        x, y = event.pos().x() - (self.width() / 2), event.pos().y() - (self.height() / 2)
        if not x == 0: 
            angle = math.atan2(y, x) / math.pi * 180
            # winkellaenge der anzeige immer positiv 0 - 360deg
            # min wert + umskalierter wert
            value = (float(math.fmod(angle - self.scale_angle_start_value + 720, 360)) / \
                     (float(self.scale_angle_size) / float(self.maxValue - self.minValue))) + self.minValue
            temp = value
            fmod = float(math.fmod(angle - self.scale_angle_start_value + 720, 360))
            state = 0
            if (self.value - (self.maxValue - self.minValue) * self.valueNeedleSnapzone) <= \
                    value <= \
                    (self.value + (self.maxValue - self.minValue) * self.valueNeedleSnapzone):
                self.NeedleColor = self.NeedleColorDrag
                # todo: evtl ueberpruefen
                #
                state = 9
                # if value >= self.maxValue and self.last_value < (self.maxValue - self.minValue) / 2:
                if value >= self.maxValue and self.last_value < (self.maxValue - self.minValue) / 2:
                    state = 1
                    value = self.maxValue
                    self.last_value = self.minValue
                    self.valueChanged.emit(int(value))

                elif value >= self.maxValue >= self.last_value:
                    state = 2
                    value = self.maxValue
                    self.last_value = self.maxValue
                    self.valueChanged.emit(int(value))


                else:
                    state = 3
                    self.last_value = value
                    self.valueChanged.emit(int(value))

                self.updateValue(value)          

    ########################################################################
    ## Misc functions
    ########################################################################

    def bound(self, low, high, value):
        return max(low, min(high, value))            

    def calc_gradiant_breaks(self, angles, lims):
        # Calculate the transition points for colors
        breaks = {}

        # Limits must be within [minval, maxval] and be ascending. To eliminate a zone just make it 1e-3 more than the last value
        minVal = lims[0]
        lowlow = lims[1]
        low = lims[2]
        high= lims[3]
        highhigh = lims[4]
        maxVal = lims[5]
        minmaxRange = maxVal - minVal

        # Numbers are in absolute (0-1 is full revolution), 
        # so we need to convert to the fraction of the circle the gague takes up
        breaks['zero']          = 1e-3
        breaks["highhigh_high"] = breaks['zero']            + (angles["span"]/360) * (maxVal - highhigh)/minmaxRange
        breaks["high_green"]    = breaks["highhigh_high"]   + (angles["span"]/360) * (highhigh - high)/minmaxRange
        breaks["low_lowlow"]    = (angles["span"]/360)      - (angles["span"]/360) * (lowlow - minVal)/minmaxRange 
        breaks["green_low"]     = breaks["low_lowlow"]      - (angles["span"]/360) * (low - lowlow)/minmaxRange
        breaks['span']          = angles["span"]/360

        for key in breaks:
            breaks[key] = self.bound(0, angles["span_norm"], breaks[key])

        # Ordered list of keys so we know what order to evaluate them in 
        breaks['orderedKeys'] = ['zero', 'highhigh_high', 'high_green', 'green_low', 'low_lowlow', 'span']            

        return breaks   

    def set_gradiant_breaks(self, angles, lims, breakColors=None):

        # Save the lims in case we want to use them to change bg color
        self.lims = lims

        breaks = self.calc_gradiant_breaks(angles, lims)

        breakVals = breaks['orderedKeys']

        if breakColors is None:
            self.breakColors = (namedColor('red'), namedColor('yellow'), namedColor('transparent'), namedColor('darkYellow'), namedColor('darkRed'))
        else:
            self.breakColors = breakColors
        
        scaleColors = []

        # Turn the break values into a list of positions and break values
        for i in range(0, len(breakVals) - 1):
            val = breaks[breakVals[i]]
            nextVal = breaks[breakVals[i + 1]]

            if not val == nextVal:
                scaleColors.append([val,       self.breakColors[i]],)
                scaleColors.append([nextVal,   self.breakColors[i]],)     

            # Make sure the values aren't on top of each other
            if len(scaleColors) >= 3:
                if isclose(scaleColors[-3][0], scaleColors[-2][0]):
                    scaleColors[-2][0] = scaleColors[-2][0] + 1e-6

        self.scale_polygon_colors = scaleColors 
        self.redrawBackground = True      
    
        #self.scale_polygon_colors = [
        #    # 0 is full CW, rotates CCW
        #    [0,                             QColor('red],
        #    [breaks["highhigh_high"],       QColor('red],
        #    [breaks["highhigh_high"] + 1e-3,QColor('yellow],
        #    [breaks["high_green"],          QColor('yellow],
        #    [breaks["high_green"] + 1e-3,   QColor('black],
        #    [breaks["green_low"],           QColor('black],
        #    [breaks["green_low"] + 1e-3,    QColor('darkYellow],
        #    [breaks["low_lowlow"],          QColor('darkYellow],    
        #    [breaks["low_lowlow"] + 1e-3,   QColor('darkRed],                                              
        #    [angles["span_norm"],           QColor('darkRed],            
        #    ]    

        self.setMinValue(lims[0])
        self.setMaxValue(lims[5])

    def checkLims(self, val):
        # Check where the values are relative to the limits, return the color
        # Exclude the lower and upper display limits
        idx = bisect_right(self.lims[1:-1], val)

        colors = (QColor('#540101'), QColor('#525201'), QColor('transparent'), QColor('#c2c202'), QColor('#cc0202'))
        # Use the break colors for the gauges
        # The problem is that yellow and red are pretty bright and wash out the needle\lettering
        #color = self.breakColors[::-1][idx] # Flip the array left-right and then return the value

        color = colors[idx]

        return color        

def namedColor(colorName):
    color2hex = {
        'white': '#ffffff',
        'darkgray': '#808080',
        'gray': '#a0a0a4',
        'lightgray': '#c0c0c0',
        'red': '#ff0000', 
        'green': '#00ff00', 
        'blue': '#0000ff',
        'cyan': '#00ffff',
        'magenta': '#ff00ff', 
        'yellow': '#ffff00', 
        'darkred': '#800000', 
        'darkgreen': '#008000', 
        'darkblue': '#000080', 
        'darkcyan': '#008080', 
        'darkmagenta': '#800080', 
        'darkyellow': '#808000', 
        'transparent': '#00000000',
    }
    if colorName.lower() in color2hex.keys():
        color = color2hex[colorName.lower()]
    else:
        color = colorName
        logging.info(f'Color {colorName} not found')

    return QColor(color)

# END ==>

