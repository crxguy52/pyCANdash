A Python GUI to decode, log, and display CAN data in real time. Intended for automotive projects, but could be used for other applications. Displays data in one of three formats - analog gauges:
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/gauges.png?raw=true)

Tiles:
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/tiles.png?raw=true)

And lists
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/lists.png?raw=true)

Also has support for reading and displaying current diagnostic troubleshooting codes (DTCs):
![alt tag](https://github.com/crxguy52/pyCANdash/blob/main/photos/DTCs.png?raw=true)

Inidividual displays can be customized via the config files in /config_files (which signals go where, what are lowlow, low, high, highhigh values and colors, etc.), and the code is written such that additional displays should be straightforward to add - CAN acquisitino and decoding are decoupled from displaying data. Log files can be played back via a setting in the config file, mostly useful for software development.

Ships with the GMLAN CAN database, used to decode 5th gen GM ECU data (LS, LFX, etc.). 
