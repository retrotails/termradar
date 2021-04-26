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

'''
	This script takes an SVG, converts the lines into a simpler format,
	and compresses them so I can reasonably fit the data into the python
	source file. It doesn't support a lot of weird SVG stuff, inkscape's
	normal SVGs should be fine though.
'''

from xml.dom import minidom
from re import split

# https://github.com/amit1rrr/numcompress/
def compress(series, precision=3):
	last_num = 0
	result = ''
	for num in series:
		diff = num - last_num
		diff = int(diff)
		diff = ~(diff << 1) if diff < 0 else diff << 1
		while diff >= 0x20:
			result += (chr((0x20 | (diff & 0x1f)) + 63))
			diff >>= 5
		result += (chr(diff + 63))
		last_num = num
	return result

outline = open("map.svg", "r")
doc = minidom.parse(outline)
path_str = [path.getAttribute("d") for path in doc.getElementsByTagName("path")]
doc.unlink()
outline.close()
out_x = []
out_y = []
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
	# Export X and Y separately for better compression
	# Also divide by 5 to save more space
	for j in range(0, len(line)-2, 2):
		out_x.append(int(line[j]/5))
		out_y.append(int(line[j+1]/5))
		out_x.append(int(line[j+2]/5))
		out_y.append(int(line[j+3]/5))

print("X:")
print(compress(out_x).replace("\\", "\\\\"))
print("Y:")
print(compress(out_y).replace("\\", "\\\\"))