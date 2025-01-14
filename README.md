A Python GUI to:
- Log, decode, and display CAN data in real time
- Analyze logged data via a web interface, which does not require any additional sofware on the viewing device

Intended for automotive projects, but could be used for other applications as well. Displays data in one of three formats - analog gauges:
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/gauges.png?raw=true)

Tiles:
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/tiles.png?raw=true)

And lists
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/lists.png?raw=true)

pyCANdash also supports reading and displaying current diagnostic troubleshooting codes (DTCs):
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/DTCs.png?raw=true)

Inidividual displays can be customized via the config files in /config_files (which signals go where, what are lowlow, low, high, highhigh values and colors, etc.), and the code is written such that additional displays should be straightforward to add - CAN acquisition and decoding are decoupled from displaying data. Log files can be played back via a setting in the config file, mostly useful for software development.

Ships with the GMLAN CAN database, used to decode 5th gen GM ECU data (LS, LFX, etc.). 

If enabled, a bokeh web server runs in the background (port 5006) and allows for easy data analysis with no additonal software. Just navigate to the devices IP address (localhost:5006 for the same PC pyCANdash is running on) in a web browser and browse all of the recorded data:
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/webViewer.png?raw=true)
