from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
)
from pyCANdash.utils import convert2ips, findUnit
from pyCANdash.analogGauges import Tach, SideGauge



class GaugeLayout1(QFrame):
    def __init__(self, gaugeCfg, canChans, colStretch=None):
        super(GaugeLayout1, self).__init__()   

        self.gaugeCfg = gaugeCfg
        self.canChans = canChans

        # Set the background color
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget { background-color: black; }")         

        # Create the gagues
        self.layout:QGridLayout = QGridLayout()        
        self.gauges = {}
        for pos in self.gaugeCfg.keys():

            lims =  gaugeCfg[pos]['lims']
            label = gaugeCfg[pos]['label']
            unit, self.gaugeCfg[pos]['scaleFactor'], self.gaugeCfg[pos]['scaleOffset'] = findUnit(gaugeCfg[pos]['signal'], canChans, useIps=gaugeCfg[pos]['convert2ips'])

            if 'center' in pos:
                # Center gauge
                self.gauges[pos] = Tach(lims, label+unit.upper(), gaugeCfg[pos]['speedUnit'])
                self.layout.addWidget(self.gauges[pos], 0, 1, 2, 1)                 

            else:
                # Side gauge
                if 'nMainDivs' in gaugeCfg[pos]:
                    self.gauges[pos] = SideGauge(lims, label+unit, nMainDivs=gaugeCfg[pos]['nMainDivs'])
                else:
                    self.gauges[pos] = SideGauge(lims, label+unit)
                row = int(pos[-2])
                col = int(pos[-1])
                self.layout.addWidget(self.gauges[pos], row, col)
   
        self.setLayout(self.layout) 
        if colStretch is not None:
            for col in range(0, len(colStretch)):
                self.layout.setColumnStretch(col, colStretch[col])
        

    def update(self, vals):
        for valDictKey in vals.keys():
            valDict = vals[valDictKey]

            for pos in self.gaugeCfg.keys():
                if self.gaugeCfg[pos]['signal'] in valDict:
                    self.gauges[pos].updateValue(
                        self.gaugeCfg[pos]['scaleFactor'] * valDict[self.gaugeCfg[pos]['signal']] + self.gaugeCfg[pos]['scaleOffset'])  

                # For the tach
                if 'speedSignal' in self.gaugeCfg[pos] and self.gaugeCfg[pos]['speedSignal'] in valDict:
                    self.gauges[pos].updateOtherValue(
                        self.gaugeCfg[pos]['speedGain'] * valDict[self.gaugeCfg[pos]['speedSignal']]) 
                    #self.gauges[pos].updateOtherValue(valDict[self.gaugeCfg[pos]['signal']]) 

                # For the tach
                if 'dynamicRedline' in self.gaugeCfg[pos]:

                    # If dynamic redline is enabled and we have a redline value from CAN data
                    if self.gaugeCfg[pos]['dynamicRedline'] and 'engine_max_speed_limit' in valDict:

                        # If it's different than the current value, update it
                        if self.gauges[pos].lims[4] != valDict['engine_max_speed_limit']:

                            tach = self.gauges[pos]
                            lims = list(tach.lims)
                            lims[3] = valDict['engine_max_speed_limit'] - 200
                            lims[4] = valDict['engine_max_speed_limit']
                            tach.set_gradiant_breaks(tach.angles, lims) 

                