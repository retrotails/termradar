# Termradar
![demo](/demo.gif?raw=true)  

Simple terminal application to download (scrape) and show NOAA weather radar animations in the terminal.
Will only work with continental US.
For usage, see "termradar.py -h"

For now, the only way to configure termradar is by editing main.py

Requirements:
* wget
* gzip (gunzip)
* Python 3
* Python libraries:
- PIL (pillow)
- numpy

Known issues:
* the SVG parser is not robust enough for some SVG weirdness,..
	like how "1.2.3" can be interpreted as [1.2, .3]..
	inkscape plain SVGs should import fine
