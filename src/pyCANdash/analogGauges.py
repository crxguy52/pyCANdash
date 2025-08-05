from pyCANdash.AnalogGaugeWidget import AnalogGaugeWidget

        
def Tach(lims, rpmUnits, speedUnits):

    tach = AnalogGaugeWidget()
    tach.setGaugeTheme(25)   

    tach.needle_scale_factor    = 0.8       # NEEDLE SCALE FACTOR/LENGTH    
    tach.needle_back_width      = 10         # Width of needle on the non-indicating side
    tach.needle_tip_width       = 5         # Width of needle at the indicating side
    tach.needle_tip_prominance  = 0         # How far to stick the center of the needle out to make it pointy
    tach.needle_back_length     = 45        # Distance from the center to the non-indicating extremity     
    tach.chngBGonVal            = True      # Update gauge background color based on value
    tach.unitAngle              = -90
    

    tach.units = rpmUnits

    angles = {}
    angles["start"] = 90
    angles["span"] = 270
    angles["span_norm"] = angles["span"]/360

    tach.lims = lims
    tach.angles = angles

    tach.set_gradiant_breaks(angles, lims) 
    tach.setScalaCount(8)      # Number of steps, not spacing  
    tach.setScalaSubDivCount(5)

    tach.scale_angle_start_value = angles["start"]
    tach.scale_angle_size = angles["span"]

    tach.setMouseTracking(False)
    tach.draw_360_bg = False

    tach.initial_scale_fontsize = 30 # default is 14

    tach.otherValEn = True
    tach.otherValAngle = 50
    tach.otherValRadScale = 0.7     # Percent of the radius to put the text
    tach.otherValFontSize = 100
    tach.otherValUnits = speedUnits

    tach.updateValue(0)  
    tach.updateOtherValue(0)   

    return tach   

def SideGauge(lims, units, nMainDivs=10):
    gauge = AnalogGaugeWidget()
    gauge.setGaugeTheme(25)     

    gauge.units = units

    angles = {}
    angles["start"] = 90 + int(45/2)   # Zero is due east
    angles["span"] = 315
    angles["span_norm"] = angles["span"]/360

    gauge.set_gradiant_breaks(angles, lims) 
    gauge.setScalaCount(nMainDivs)      # Number of steps, not spacing  
    gauge.setScalaSubDivCount(5)
    gauge.unitAngle = 90
    gauge.scale_text_radius_factor = 0.75  
    gauge.enable_value_text = False

    gauge.initial_scale_fontsize = 25 # default is 14

    gauge.scale_angle_start_value = angles["start"]
    gauge.scale_angle_size = angles["span"]

    gauge.setMouseTracking(False)

    gauge.updateValue(0)     

    return gauge   

