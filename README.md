# Termradar
![demo](/demo.gif?raw=true)  

Simple terminal application to download (scrape) and show NOAA weather radar animations in the terminal.
Will only work with contiguous US.
For usage, see "termradar.py -h"

See configuration in ~/.config/termradar/config after running it once
Set the rectangle you want to see by opening util/map.png in an image editor and making note of the pixel coordinates.
Set "rect" to the appropriate X, Y, width, and height (in that order) where 0,0 is in the top-left.
You can also add pins, which will add a blinking character, generally to represent your approximate location.

Requirements:
* wget
* gzip (gunzip)
* Python 3
* Python libraries:
  * PIL (pillow)
  * numpy

termradar is set up to be distributed as a single python file with everything built-in.

Known issues:
* The SVG parser is not robust enough for some SVG weirdness,..
	like how "1.2.3" can be interpreted as [1.2, .3]..
	inkscape plain SVGs should import fine
* Doesn't render correctly in some terminals (as a fallback, use --lowres)