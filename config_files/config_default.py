# This is formatted as a dictionary
{
    # Plays back log file for debug (must include file extension). May be deleted or set to None to disable. Skips time gaps >5s 
    #"playbackFn":       "20241124_141123.log",  
    "startTab":         3,                  # Tab to display at startup
    "dataDir":          "/mnt/usb_drive/",  # Path to where data gets saved. if None (or path is invalid) internal data directory is used.
                                            # Used by everything - bokeh server, CAN logging, loguploader, etc.

    'bokehServer':{                             # Bokeh web server to view recorded data
        'enable':       True,                   # Enable it?
        'dbcName':      'gmlan_v1.6',           # Which can DBC file to use
        'IPs':          ["192.168.10.1:5006"],  # IP addresses to host the server on in addition to the local IP and localhost 
    },

    'httpServer':{                              # http server to allow for easy data download
        'enable':       True,                   # Enable it?
        'port':         8000,                   # port to serve on
    },    

    # Option to upload log files via FTP to a remote server
    'logUploader':{
        'ip':           '192.168.0.1',          # FTP copy disabled if IP is None
        'remoteLogDir': '/G/CAN_logs',           # Where on the remote server to store CAN logs. Must start with /
    },    

    'odometer':{ 
        'enable':       True,                           # Enable the odometer?
        'signalName':   'vehicle_speed_avg_driven',     # Signal name used for incrementing odometer, speed
    },       

    # Monitor a GPIO (power) pin and shut down if it's low for more than lowTime seconds
    'GPIOmonitor':{
        'Enable':       False,      # Enable monitoring of GPIO to shutdown Pi?
        'gpioPin':      1,          # What pin to monitor?
        'lowTime':      20,         # How long the pin must be low (continuously) to shut down
        'Ts':           40e-3,      # How often to check the status of the pin
    },    

    # NOTE: signal names MUST be unique across all CAN databases
    'canChans':{
        # Physical channel: params
        'GMLAN':{
            'name':         'GMLAN',
            'interface':    'socketcan',
            'channel':      'can0',
            'baud':         500000,
            'dbcName':      'gmlan_v1.6',
            'arbIDdtc':     1906,           # Arbitration ID for diagnostic troubleshooting codes (DTCs). Set to -1 if unused
            'RxHz':         60,             # How frequently for the worker to grab CAN data from the hardware. Do it at least as fast as the fastest update interval
            'logFormat':    'blf'           # File type to log to. Should be one of those defined here: https://python-can.readthedocs.io/en/stable/file_io.html#can.Logger
                                            # Tested with 'log' and 'blf' formats, blf format is 92% smaller than a text format with default compression
        },
        # Uncomment if a second CAN channel is used
        # 'ABS':{
        #     'name':         'ABS',
        #     'interface':    'socketcan',
        #     'channel':      'can1',
        #     'baud':         500000,
        #     'dbcName':      'gmlan_v1.4',
        #     'arbIDdtc':     -1,             # Arbitration ID for diagnostic troubleshooting codes (DTCs). Set to -1 if unused
        #     'RxHz':         60,              # How frequently for the worker to grab CAN data from the hardware. Do it at least as fast as the fastest update interval
        #     'logFormat':    'log'           # File type to log to. Should be one of those defined here: https://python-can.readthedocs.io/en/stable/file_io.html#can.Logger
        #                                     # Tested with 'log' and 'blf' formats, blf format is 92% smaller than a text format with default compression
        # },        
    },

    "tabCfg":{
        0:{
        'name':     "Overview",
        'dispHz':   15,            # How frequently to update the display with new CAN data
        'cellCfg':{

            # llim      = lower display limit (for gagues)
            # lowlow    = start of dark red area
            # low       = start of dark yellow area
            # high      = start of yellow area
            # highhigh  = start of red area
            # ulim  = upper display limit (for gagues)

            'bgColors':('darkRed', 'darkYellow', 'transparent', 'yellow', 'red'),
            'fontColors':('white', 'white',      'white',       'black',  'black'),
                                                
            '0,0':{                                     # row,col
                'sigName':'eng_speed',               # Signal name in the db
                'dispName':'Engine Speed',              # display name  
                'lims':(-1, -1, -1, 7000, 7200, 8000),  # llim, lowlow, low, high, highhigh, ulim 
                'dispFmt':'%1.0f',                      # Display format
                'convert2ips':False,                    # Convert to inch pound second units when displaying? If true, limits are in ips units, not database units
                },
            '0,1':{'sigName':'accelerator_actual_pos',      'dispName':'Accelerator Pos',   'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f', 'convert2ips':False,},
            '0,2':{'sigName':'throttle_pos',                'dispName':'Throttle Pos',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f', 'convert2ips':False,},
            '0,3':{'sigName':'vehicle_speed_avg_driven',    'dispName':'Speed',             'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f', 'convert2ips':False,},
            '1,0':{'sigName':'eng_max_speed_limit',      'dispName':'Max Eng Speed',     'lims':(-1e3, -999, 	0, 		10e3,	10e3, 2001),'dispFmt':'%1.0f', 'convert2ips':False,},
            '1,1':{'sigName':'eng_intake_air_temp',      'dispName':'Intake Air Temp',   'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
            '1,2':{'sigName':'eng_manifold_abs_pres',    'dispName':'Manifold Press abs','lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
            '1,3':{'sigName':'commanded_air_fuel_ratio',    'dispName':'Commanded AFR',     'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},   
            '2,0':{'sigName':'eng_oil_pressure',         'dispName':'Oil Press',         'lims':(0, 6, 8, 80, 90, 100),                      'dispFmt':'%1.1f', 'convert2ips':True,},
            '2,1':{'sigName':'ambient_air_temp',            'dispName':'Ambient Air Temp',  'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
            '2,2':{'sigName':'mass_air_flow',               'dispName':'Mass Airflow',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
            '2,3':{'sigName':'fuel_alcohol_composition',    'dispName':'Fuel Alcohol',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},  
            '3,0':{'sigName':'eng_oil_temperature',      'dispName':'Oil Temp Est',      'lims':(0, 0, 75, 125, 135, 200),                   'dispFmt':'%1.1f', 'convert2ips':False,},
            '3,1':{'sigName':'eng_coolant_temp',         'dispName':'Coolant Temp',      'lims':(0, 0, 75, 110, 130, 200),                   'dispFmt':'%1.1f', 'convert2ips':False,},
            '3,2':{'sigName':'trans_oil_temp',              'dispName':'Trans Temp',        'lims':(0, 0, 15, 100, 175, 200),                   'dispFmt':'%1.1f', 'convert2ips':False,},
            '3,3':{'sigName':'check_engine_ind_on',         'dispName':'Check Engine',      'lims':(-1e3, -999, 	-1,		1,	    2,      3), 'dispFmt':'%1.0f', 'convert2ips':False,},
        }
        },
        1:{
            'name':'Measurements',
            'dispHz':15,            # How frequently to update the display with new CAN data            
            'cellCfg':{        
                'leftCol':{ 
                    # Left column
                    # Row: message                                                                              
                    'bgColors':('darkRed', 'darkYellow', 'transparent', 'yellow', 'red'),                   # llim, lowlow,   low,    high,   highhigh,   ulim 
                    'fontColors':('white', 'white',      'white',       'black',  'black'),
                    0:{ 'sigName':'eng_speed',                'dispName':'Engine Speed',      'lims':(-1,    -1,	    -1,     7000,	7200,   8000), 'dispFmt':'%1.0f', 'convert2ips':False,},
                    1:{ 'sigName':'accelerator_actual_pos',      'dispName':'Accelerator Pos',   'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f', 'convert2ips':False,},
                    2:{ 'sigName':'throttle_pos',                'dispName':'Throttle Pos',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f', 'convert2ips':False,},
                    3:{ 'sigName':'mass_air_flow',               'dispName':'Mass Airflow',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},   
                    4:{ 'sigName':'barometric_pressure_abs',     'dispName':'Baro Press abs',    'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
                    5:{ 'sigName':'eng_intake_air_boost_press',  'dispName':'Manifold Boost',    'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
                    6:{ 'sigName':'eng_manifold_abs_pres',    'dispName':'Manifold Press abs','lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},
                    7:{ 'sigName':'eng_intake_air_temp',      'dispName':'Intake Air Temp',   'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f', 'convert2ips':False,},     
                    8:{ 'sigName':'ambient_air_temp',            'dispName':'Ambient Air Temp',  'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f' , 'convert2ips':False,},
                    9:{ 'sigName':'fuel_alcohol_composition',    'dispName':'Fuel Alcohol',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f' , 'convert2ips':False,},
                    10:{'sigName':'eng_coolant_temp',         'dispName':'Coolant Temp',      'lims':(0, 0, 75, 110, 130, 200),                  'dispFmt':'%1.1f' , 'convert2ips':False,},
                    11:{'sigName':'eng_oil_temperature',      'dispName':'Oil Temp Est',      'lims':(0, 0, 75, 125, 135, 200),                  'dispFmt':'%1.1f' , 'convert2ips':False,},   
                    12:{'sigName':'eng_oil_pressure',         'dispName':'Oil Press',         'lims':(0, 6, 8, 80, 90, 100),                     'dispFmt':'%1.1f' , 'convert2ips':True,},
                    13:{'sigName':'trans_oil_temp',              'dispName':'Trans Temp',        'lims':(0, 0, 15, 100, 175, 200),                  'dispFmt':'%1.1f' , 'convert2ips':False,},
                    14:{'sigName':'commanded_air_fuel_ratio',    'dispName':'Commanded AFR',     'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.1f' , 'convert2ips':False,},        
                },
                'rightCol':{ # Right column
                    # Row: message
                    'bgColors':('darkRed', 'darkYellow', 'transparent', 'yellow', 'red'),
                    'fontColors':('white', 'white',      'white',       'black',  'black'),
                    0:{'sigName':'trans_estimated_gear',             'dispName':'Est Gear',      'lims':(-1e3, -999, 	-1,		7,	    7,  2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    1:{'sigName':'vehicle_speed_avg_driven',         'dispName':'Speed',         'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    2:{'sigName':'fuel_level_percent',               'dispName':'Fuel Level',    'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    3:{'sigName':'ac_refrigerant_high_side_press',   'dispName':'AC Press',      'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},   
                    4:{'sigName':'fuel_pmp_en_discrete_output',      'dispName':'Fuel Pump En',  'lims':(-1e3, -1, 	    0, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    5:{'sigName':'fuel_pressure_requested',          'dispName':'Fuel Pres Req', 'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    6:{'sigName':None,                               'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    7:{'sigName':None,                               'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},     
                    8:{'sigName':None,                               'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    9:{'sigName':None,                               'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    10:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    11:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},   
                    12:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    13:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    14:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                },
            },
        },
        2:{
            'name':'Status',
            'dispHz':15,            # How frequently to update the display with new CAN data        
            'cellCfg':{        
                'leftCol':{ # Left column
                    # Row: message
                    'bgColors':('darkRed', 'darkYellow', 'transparent', 'yellow', 'red'),
                    'fontColors':('white', 'white',      'white',       'black',  'black'),
                    0:{'sigName':'eng_speed_status',             'dispName':'Engine Speed Stat',     'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    1:{'sigName':'eng_fuel_control_state',       'dispName':'Fuel Ctrl State',       'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    2:{'sigName':'reduced_power_indicator',         'dispName':'Reduced Power',         'lims':(-1e3, -999, 	-1,		1,	    2,      3), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    3:{'sigName':'check_engine_ind_on',             'dispName':'Check Engine',          'lims':(-1e3, -999, 	-1,		1,	    2,      3), 'dispFmt':'%1.0f' , 'convert2ips':False,},   
                    4:{'sigName':'eng_max_speed_limit',          'dispName':'Max Eng Speed',         'lims':(-1e3, -999, 	0, 		10e3,	10e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    5:{'sigName':'throttle_progression_status',     'dispName':'Throttle Prog',         'lims':(-1e3, -999, 	0, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    6:{'sigName':'eng_coast_fuel_cutoff_active', 'dispName':'Eng Coast Fuel Cut',    'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    7:{'sigName':'fuel_pmp_en_discrete_output',     'dispName':'Fuel Pump Output En',   'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},     
                    8:{'sigName':'eng_oil_hot_indicator_on',     'dispName':'Hot Oil Indicator',     'lims':(-1e3, -999, 	-1,		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    9:{'sigName':'eng_oil_pres_low_indicator_on','dispName':'Low Oil Press Ind',     'lims':(-1e3, -999, 	-1,		1,	    2,   3), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    10:{'sigName':'eng_oil_starvation_indication_on','dispName':'Oil Starvation Ind',    'lims':(-1e3, -999, 	-1, 		1,	    2,   3), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    11:{'sigName':'eng_hot_stop_engine_ind_on',   'dispName':'Engine Hot Stop Ind',   'lims':(-1e3, -999, 	-1,		1,	    2,   3), 'dispFmt':'%1.0f' , 'convert2ips':False,},   
                    13:{'sigName':None,                              'dispName':'',                      'lims':(-1e3, -999, 	0, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    14:{'sigName':None,                              'dispName':'',                      'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},   
                },
                'rightCol':{ # Right column
                    # Row: message
                    'bgColors':('darkRed', 'darkYellow', 'transparent', 'yellow', 'red'),
                    'fontColors':('white', 'white',      'white',       'black',  'black'),
                    0:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    1:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    2:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    3:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},  
                    4:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    5:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    6:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    7:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},     
                    8:{'sigName':None,                              'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    9:{ 'sigName':None,                             'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    10:{'sigName':None,                             'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    11:{'sigName':None,                             'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},   
                    12:{'sigName':None,                             'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    13:{'sigName':None,                             'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                    14:{'sigName':None,                             'dispName':'',              'lims':(-1e3, -999, 	1, 		1500,	2e3, 2001), 'dispFmt':'%1.0f' , 'convert2ips':False,},
                },
            },
        },
        3:{
            'name':'Digital Dash',
            'dispHz':60,                # How frequently to update the display with new CAN data
            'colStretch':[1, 3, 1],     # Column stretch values, how wide to make each column
            'gaugeCfg':{
                # Origin is in the top left, so 00 is the top left gauge. Center gague is col 1, right gauges are col 2
                'sideGauge00':{'signal':'eng_oil_temperature',   'lims':(60, 60, 75, 125, 135, 140),   'label':'Oil\n', 'convert2ips':False, 'nMainDivs':8,},
                'sideGauge10':{'signal':'eng_oil_pressure',      'lims':(0, 10, 15, 120, 130, 140),      'label':'Oil\n', 'convert2ips':True, 'nMainDivs':14,},                         
                'sideGauge02':{'signal':'eng_coolant_temp',      'lims':(60, 60, 75, 115, 120, 140),   'label':'Water\n', 'convert2ips':False, 'nMainDivs':8,},
                'sideGauge12':{'signal':'trans_oil_temp',        'lims':(20, 20, 15, 100, 110, 120),   'label':'Trans\n', 'convert2ips':False, 'nMainDivs':10,},
                'centerGauge':{'signal':'eng_speed',             'lims':(0, 0, 0, 6.8, 7.2, 8), 'label':'', 'convert2ips':True,        # if convert2ips is true, converts to kRPM
                                'speedSignal':'vehicle_speed_avg_driven', 'dynamicRedline':True, 'speedUnit':'MPH', 'speedGain':0.621371},  # MPH per kph     
                                # speed stuff is a hack but also I don't feel like doing it a better way
            }
        },   
        # 4:{
        #     'name':'DTCs',
        #     'dispHz':10,            # How frequently to update the display with new CAN data
        #     'colCfg':{
        #         0:{'DisplayName':   'Number',                               'sigName': 'diag_trouble_code_number'},
        #         1:{'DisplayName':   'Triggered?',                           'sigName': 'diag_trouble_code_triggered'},
        #         2:{'DisplayName':   'Code supported?',                      'sigName': 'diag_code_supported'},            
        #         3:{'DisplayName':   'Current Status',                       'sigName': 'diag_current_status'},            
        #         4:{'DisplayName':   'Warn Ind Req?',                        'sigName': 'diag_warn_ind_reqested_stat'},            
        #         5:{'DisplayName':   'Source',                               'sigName': 'diag_trouble_code_source'},
        #         6:{'DisplayName':   'Fail Type',                            'sigName': 'diag_trouble_code_fail_type'},
        #         7:{'DisplayName':   'Fault Type',                           'sigName': 'diag_trouble_code_fault_type'},            
        #         8:{'DisplayName':   'Failed since power up?',               'sigName': 'diag_tst_fail_since_pwrup_stat'},
        #         9:{'DisplayName':   'Test not passed since code cleared?',  'sigName': 'diag_tst_nopass_since_pwrup_stat'},
        #     },
        # },                
    },
}












