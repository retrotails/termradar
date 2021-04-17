#!/usr/bin/env python3
'''
    termradar, NOAA radar images for your terminal
    Copyright (C) 2021 retrotails

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, version 3.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

from os import get_terminal_size, path, makedirs, remove
from re import split, search
from time import sleep
from math import floor
from xml.dom import minidom
from PIL import Image
from argparse import ArgumentParser
import numpy as np
from subprocess import run, PIPE
from glob import glob
def clamp(v,n,x):
	return min(max(v,n),x)

### Start configuration ###



# Crop map to your area, using X/Y/W/H
rect = [300,1000,1000,1500]
# Pixel position of flashing pins to place on the map
pins = [
	[1100, 2050],
	[800, 1777]
]
# Map resolution
res_img = [7000, 3500]

# col_actual is the RGB values for your actual terminal colors,
# used to find the closest color for approximation of the image.
# You can put the hex color codes for your terminal theme here,
# if you want the map colors to match better
col_actual = [
	[0x00,0x00,0x00], # black
	[0xaa,0x00,0x00], # red
	[0x00,0xaa,0x00], # green
	[0xaa,0xaa,0x00], # orange
	[0x00,0x00,0xaa], # blue
	[0xaa,0x00,0xaa], # purple
	[0x00,0xaa,0xaa], # cyan
	[0xaa,0xaa,0xaa], # grey
	[0x55,0x55,0x55], # dark grey
	[0xff,0x55,0x55], # light red
	[0x55,0xff,0x55], # light green
	[0xff,0xff,0x55], # yellow
	[0x55,0x55,0xff], # light blue
	[0xff,0x55,0xff], # light purple
	[0x55,0xff,0xff], # light cyan
	[0xff,0xff,0xff], # white
]
col_actual = np.array(col_actual)


### End configuration ###


# Find cache directory
from xdg.BaseDirectory import xdg_cache_home
if "xdg_cache_home" in locals():
	cache_dir = xdg_cache_home
else:
	from path import expanduser
	cache_dir = expanduser("~/.cache")
cache_dir = path.join(cache_dir, "termradar")
if not path.exists(cache_dir):
	err = makedirs(cache_dir, 0o755, True)
	if (err):
		raise ValueError("Error: \"" + cache_dir + "\" could not be created (" + err +")")


# https://stackoverflow.com/questions/54242194/python-find-the-closest-color-to-a-color-from-giving-list-of-colors/54244301#54244301
def closest(color):
	color = np.array(color)
	distances = np.sqrt(np.sum((col_actual-color)**2,axis=1))
	# now, why I need to get [0][0], I have no idea
	return np.where(distances==np.amin(distances))[0][0]

def is_int(i):
	try:
		int(i)
		return True
	except ValueError:
		return False

parser = ArgumentParser(
	description="Show NOAA radar images in the commandline"
)
parser.add_argument(
	"--lowres",
	help="Don't use unicode characters to double resolution",
	action="store_true"
)
parser.add_argument(
	"--size",
	help="Size (in characters) to render (Default: Fill terminal window)",
	metavar="WxH"
)
parser.add_argument(
	"--lines",
	help="State outlines. Options: top/above, bottom/below, none (Default: top)"
)
parser.add_argument(
	"--nopins",
	help="Don't draw blinking pins",
	action="store_true"
)
parser.add_argument(
	"--anim",
	help="Download older frames and show animation (download and display intensive!)",
	action="store_true"
)
parser.add_argument(
	"--all",
	help="Show entire continental US",
	action="store_true"
)
parser.add_argument(
	"--update",
	help="Download new images",
	action="store_true"
)
parser.add_argument(
	"--frames",
	help="Number of frames to animate (1 to 6, Default: 3)"
)

args = parser.parse_args()

# Terminal control characters for the various colors
col_fg = [
	"\033[1;30m",
	"\033[1;31m",
	"\033[1;32m",
	"\033[1;33m",
	"\033[1;34m",
	"\033[1;35m",
	"\033[1;36m",
	"\033[1;37m",

	"\033[1;90m",
	"\033[1;91m",
	"\033[1;92m",
	"\033[1;93m",
	"\033[1;94m",
	"\033[1;95m",
	"\033[1;96m",
	"\033[1;97m",
]
col_bg = [
	"\033[0;40m",
	"\033[0;41m",
	"\033[0;42m",
	"\033[0;43m",
	"\033[0;44m",
	"\033[0;45m",
	"\033[0;46m",
	"\033[0;47m",

	"\033[0;100m",
	"\033[0;101m",
	"\033[0;102m",
	"\033[0;103m",
	"\033[0;104m",
	"\033[0;105m",
	"\033[0;106m",
	"\033[0;107m",
]

res = [0,0]
res_scale = 0
offset = [0,0]
canvas = []

res_term = [get_terminal_size().columns, get_terminal_size().lines]

if args.size:
	s = split('x',args.size)
	if (is_int(s[0]) and is_int(s[1])):
		res_term = [int(s[0]), int(s[1]) ]
	else:
		print("Error: Invalid size")
		quit()
if args.all:
	rect = [0, 0, res_img[0], res_img[1]]

res_term[1] = res_term[1] * 2
if (res_term[0] < 16 or res_term[1] < 16):
	print("Size too small (<16)")
	quit()

# Hard resolution limit
res_term[0] = min(res_term[0], 512)
res_term[1] = min(res_term[1], 1024)


# TODO expand the rect[] to fill the screen aspect ratio

res_scale = min(res_term[0]/rect[2], res_term[1]/rect[3])
res = [
	floor(res_scale*rect[2]),
	floor(res_scale*rect[3])
]

def get_map(frames, location):
	base_url = "https://mrms.ncep.noaa.gov/data/RIDGEII/L2/CONUS/CREF_RAW/"
	def get_tif(url):
		tif = run(["wget", "-O", "-", "-o", "/dev/null", base_url + url + ".tif.gz"], check=True, capture_output=True)
		out = run(["gunzip", "-c"], input=tif.stdout, capture_output=True)
		return out.stdout
	for f in glob(location + "/" + "*.tif"):
		remove(f)
	# Get latest list of images
	result = run(["wget", "-O", "-", "-o", "/dev/null", base_url], stdout=PIPE)
	files = []
	for line in str(result).split('\\n'):
		if ".tif.gz" in line:
			files.append(search('<a href="(.*).tif.gz">', line).group(1))
	# Download and save to file
	i = 0
	for f in range(frames):
		print("Downloading frame " + str(f))
		fil = open(path.join(location, str(i) + ".tif"), "wb")
		fil.write(get_tif(files[-(i*4 + 1)]))
		fil.close()
		i += 1

def set_pixel(x,y,c):
	global canvas
	if x >= 0 and x < res[0] and y >= 0 and y < res[1]:
		canvas[y*res[0] + x] = c

def draw_line(x0, y0, x1, y1):
	x0 = floor((x0-rect[0])*res_scale)
	y0 = floor((y0-rect[1])*res_scale)
	x1 = floor((x1-rect[0])*res_scale)
	y1 = floor((y1-rect[1])*res_scale)
	set_pixel(x1, y1, 0xf)

	steep = abs(y1 - y0) > abs(x1 - x0)

	if steep:
		x0, y0 = y0, x0
		x1, y1 = y1, x1
	if x0 > x1:
		x0, x1 = x1, x0
		y0, y1 = y1, y0

	dx = x1 - x0
	dy = abs(y1 - y0)
	error = dx / 2
	y = y0

	if y0 < y1: ystep = 1 
	else: ystep = -1

	for x in range(x0, x1):
		if steep: set_pixel(floor(y), floor(x), 0xf)
		else: set_pixel(floor(x), floor(y), 0xf)
		error -= dy
		if error < 0:
			y += ystep
			error += dx

# Render SVG to terminal
def get_outline(): 
	outline = open("map.svg", "r")
	doc = minidom.parse(outline)
	path_str = [path.getAttribute("d") for path in doc.getElementsByTagName("path")]
	doc.unlink()
	outline.close()

	for path in path_str:
		if path[0] != "m" and path[0] != "M":
			raise Exception("Invalid path found in \"" + name + "\" outline. Check SVG file.")
		path_split = split('.(?=[MmLlHhVvCcSsQqTtAaZz])', path)

		turtle = [0,0]
		line = []
		for node in path_split:
			typ = node[0]
			if len(node) > 1:
				points = split(' |,|\n',node[1:].strip())
				points = list(map(float, points))
				
			if typ == "m" or typ == "l": # TODO lol
				for i in range(0,len(points),2):
					turtle[0] += points[i]
					line.append(turtle[0])
					turtle[1] += points[i+1]
					line.append(turtle[1])
					
			elif typ == "h":
				for point in points:
					turtle[0] += point
					line.append(turtle[0]) # X
					line.append(line[-2])  # Y
			elif typ == "H":
				for point in points:
					turtle[0] = point
					line.append(turtle[0]) # X
					line.append(line[-2])  # Y
				
			elif typ == "v":
				for point in points:
					line.append(line[-2])  # X
					turtle[1] += point
					line.append(turtle[1]) # Y
			elif typ == "V":
				for point in points:
					line.append(line[-2])  # X
					turtle[1] = point
					line.append(turtle[1]) # Y
				
			elif typ == "M" or typ == "L": # TODO lol
				x = True
				turtle[0] = points[-2]
				turtle[1] = points[-1]
				for i in points:
					line.append(i)
					
			elif typ == "Z" or typ == "z":
				line.append(line[0])
				line.append(line[1])
				turtle[0] = line[0]
				turtle[1] = line[1]
		for j in range(0, len(line)-2, 2):
			draw_line(line[j], line[j+1], line[j+2], line[j+3])

def get_radar(index):
	cref = Image.open(path.join(cache_dir, str(index) + ".tif"))
	#=cref.convert("RGBA")
	out = cref.resize(
		(res[0], res[1]),
		box=(rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3]),
		resample=0
	)
	# debug
	# out.save("resize-output.png")
	w,h = out.size
	px = out.load()
	for y in range(0,h):
		for x in range(0,w):
			r,g,b,a = px[x,y]
			if a > 0:
				set_pixel(x,y,closest([r,g,b]))

def get_str(index):
	global canvas
	canvas = [0] * (res[0]*res[1])
	if args.lines:
		if args.lines == "top" or args.lines == "above":
			get_radar(index)
			get_outline()
		elif args.lines == "bottom" or args.lines == "below":
			get_outline()
			get_radar(index)
		else:
			get_radar(index)
			
	else:
		get_radar(index)
		get_outline()
	if not args.nopins:
		for p in pins:
			set_pixel(
				floor((p[0] - rect[0])*res_scale),
				floor((p[1] - rect[1])*res_scale),
				"blink"
			)

	string = ""
	for y in range(0, res[1]-2, 2):
		string += "\n"
		for x in range(res[0]):
			pixel1 = canvas[ y   *res[0] + x]
			pixel2 = canvas[(y+1)*res[0] + x]
			if (pixel1 == "blink" or pixel2 == "blink"):
				string += col_bg[0]
				string += "\033[93;5m"
				string += chr(0x2588)
				string += col_bg[0]
			else:
				if args.lowres:
					if pixel2 == 15:
						# fix holes in lines
						string += col_fg[15]
					else:
						string += col_fg[pixel1]
					string += chr(0x2588)
				else:
					string += col_bg[pixel2]
					string += col_fg[pixel1]
					string += chr(0x2580)
		string += "\033[0;30m"
	return string

if args.update:
	frames = 1
	if args.anim:
		frames = 3
	if args.frames:
		frames = clamp(int(args.frames), 1, 6)
	get_map(frames, cache_dir)
elif len(glob(cache_dir + "/*.tif")) == 0:
	print("Error: No images, please use --update")
	exit()
if args.anim:
	anim = []
	# For each tif file in cache_dir
	for i in range(len(glob(cache_dir + "/*.tif"))-1, -1, -1):
		print("Generating frame " + str(i))
		anim.append(get_str(i))
	while True:
		for i in anim:
			print(i)
			sleep(0.5)
		sleep(1.5)
else:
	print(get_str(0))