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
from os.path import expanduser
from re import split, search
from time import sleep
from math import floor
from PIL import Image
from argparse import ArgumentParser
import numpy as np
from subprocess import run, PIPE
from glob import glob
from configparser import ConfigParser
config = ConfigParser()
def clamp(v,n,x): return min(max(v,n),x)

# Map resolution
res_img = [7000, 3500]

# Find config directory
from xdg.BaseDirectory import xdg_config_home
if "xdg_config_home" in locals(): conf_dir = xdg_config_home
else: conf_dir = expanduser("~/.config")
conf_dir = path.join(conf_dir, "termradar")
if not path.exists(conf_dir):
	err = makedirs(conf_dir, 0o755, True)
	if (err):
		raise ValueError("Error: \"" + conf_dir + "\" could not be created (" + err +")")

# Do the same, find cache directory
from xdg.BaseDirectory import xdg_cache_home
if "xdg_cache_home" in locals(): cache_dir = xdg_cache_home
else: cache_dir = expanduser("~/.cache")
cache_dir = path.join(cache_dir, "termradar")
if not path.exists(cache_dir):
	err = makedirs(cache_dir, 0o755, True)
	if (err):
		raise ValueError("Error: \"" + cache_dir + "\" could not be created (" + err +")")

# Create default config file
if not path.exists(path.join(conf_dir, "config")):
	with open(path.join(conf_dir, "config"),"a+") as f:
		f.write(
			"[main]\n"
			"rect=300,1000,1000,1500\n"
			"pins=1100,2050;800,1777\n"
			"termcolors=000000,aa0000,00aa00,aaaa00,0000aa,aa00aa,00aaaa,aaaaaa,"
				"555555,ff5555,55ff55,ffff55,5555ff,ff55ff,55ffff,ffffff\n"
		)

# Load config file
try: config.read(path.join(conf_dir, "config"))
except:
	print("Could not parse config file, \"" + path.join(conf_dir, "config") + "\", try deleting it.")
	exit(1)

# Check if configuration is valid
rect = []
for i in split(",", config.get("main", "rect")): rect.append(int(i))
if not (
	rect[0] > 0 and rect[0] + rect[2] < res_img[0] and
	rect[1] > 0 and rect[1] + rect[3] < res_img[1]
):
	print("Invalid view rectangle ({0})".format(rect))
	print("Can't be negative and must be within map size. ({0} x {1})".format(res_img[0], res_img[1]))
	exit(1)

pins = []
for i in split(";", config.get("main", "pins")):
	p = []
	for s in split(",", i):
		p.append(int(s))
	pins.append(p)
# TODO check if pins are valid

# import terminal colors from config
# https://stackoverflow.com/questions/54242194/python-find-the-closest-color-to-a-color-from-giving-list-of-colors/54244301#54244301
def closest(color):
	# clamp out the mostly useless "colder" colors that are just noise
	if color[0]*2 + color[1]*0.5 - color[2]*2 < 128: return 0
	color = np.array(color)
	distances = np.sqrt(np.sum((col_actual-color)**2,axis=1))
	return np.where(distances==np.amin(distances))[0][0]
# convert "#rrggbb" to "[0xrr, 0xgg, 0xbb]" for numpy
col_actual = split(",", config.get("main", "termcolors"))
if len(col_actual) != 16:
	print("\"termcolors\" configuration option needs 16 values (has " + str(len(col_actual)) + "). Try deleting " + conf_dir)
	exit(1)
for c in range(len(col_actual)):
	col_actual[c] = [
		int(col_actual[c][0:2], 16),
		int(col_actual[c][2:4], 16),
		int(col_actual[c][4:6], 16),
	]
col_actual = np.array(col_actual)



def is_int(i):
	try: int(i); return True
	except ValueError: return False

parser = ArgumentParser(description="Show NOAA radar images in the commandline")
parser.add_argument("--lowres",
	help="Don't use unicode characters to double resolution",
	action="store_true")
parser.add_argument("--size",
	help="Size (in characters) to render (Default: Fill terminal window)",
	metavar="WxH")
parser.add_argument("--lines",
	help="State outlines. Options: top/above, bottom/below, none (Default: top)")
parser.add_argument("--nopins",
	help="Don't draw blinking pins",
	action="store_true")
parser.add_argument("--anim",
	help="Download older frames and show animation (download and display intensive!)",
	action="store_true")
parser.add_argument("--frames",
	help="Number of frames to animate (1 to 6, Default: 3)")
parser.add_argument("--all",
	help="Show entire contiguous US",
	action="store_true")
parser.add_argument("--update",
	help="Download new images (Entire US radar is cached, only run this when data is stale!)",
	action="store_true")

args = parser.parse_args()

# Terminal control characters for the various colors
col_fg = [
	"\033[1;30m","\033[1;31m","\033[1;32m","\033[1;33m",
	"\033[1;34m","\033[1;35m","\033[1;36m","\033[1;37m",
	"\033[1;90m","\033[1;91m","\033[1;92m","\033[1;93m",
	"\033[1;94m","\033[1;95m","\033[1;96m","\033[1;97m",
]
col_bg = [
	"\033[0;40m","\033[0;41m","\033[0;42m","\033[0;43m",
	"\033[0;44m","\033[0;45m","\033[0;46m","\033[0;47m",
	"\033[0;100m","\033[0;101m","\033[0;102m","\033[0;103m",
	"\033[0;104m","\033[0;105m","\033[0;106m","\033[0;107m",
]

res = [0,0]
res_scale = 0
offset = [0,0]
canvas = []

res_term = [get_terminal_size().columns, get_terminal_size().lines]

# Check terminal size
if args.size:
	s = split('x',args.size)
	if (is_int(s[0]) and is_int(s[1])):
		res_term = [int(s[0]), int(s[1]) ]
	else:
		print("Error: Invalid size")
		exit(1)
if args.all: rect = [0, 0, res_img[0], res_img[1]]
res_term[1] = res_term[1] * 2
if (res_term[0] < 16 or res_term[1] < 16):
	print("Terminal window too small (<16x16)")
	exit(1)

# Hard resolution limit
res_term[0] = min(res_term[0], 512)
res_term[1] = min(res_term[1], 1024)

res_scale = min(res_term[0]/rect[2], res_term[1]/rect[3])
res = [
	floor(res_scale*rect[2]),
	floor(res_scale*rect[3])
]


# Scrape TIF images from NOAA using some lazy commands
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
	if steep: x0, y0, x1, y1 = y0, x0, y1, x1
	if x0 > x1: x0, x1, y0, y1 = x1, x0, y1, y0
	dx,dy = x1 - x0, abs(y1 - y0)
	error = dx / 2
	y = y0
	if y0 < y1: ystep = 1 
	else: ystep = -1
	for x in range(x0, x1):
		if steep: set_pixel(floor(y), floor(x), 0xf)
		else: set_pixel(floor(x), floor(y), 0xf)
		error -= dy
		if error < 0: y += ystep; error += dx

def draw_outline():
	for l in range(len(lines_x)):
		for j in range(len(lines_x[l])-1):
			draw_line(
				lines_x[l][j]  *5,lines_y[l][j]  *5,
				lines_x[l][j+1]*5,lines_y[l][j+1]*5
			)

def get_radar(index):
	cref = Image.open(path.join(cache_dir, str(index) + ".tif"))
	# Use PIL to crop and resize radar image to fit terminal
	out = cref.resize(
		(res[0], res[1]),
		box=(rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3]),
		resample=0
	)
	w,h = out.size
	px = out.load()
	for y in range(0,h):
		for x in range(0,w):
			r,g,b,a = px[x,y]
			if a > 0: set_pixel(x,y,closest([r,g,b]))

def get_str(index):
	global canvas
	canvas = [0] * (res[0]*res[1])
	if args.lines:
		if args.lines == "top" or args.lines == "above":
			get_radar(index)
			draw_outline()
		elif args.lines == "bottom" or args.lines == "below":
			draw_outline()
			get_radar(index)
		else: get_radar(index)
	else: get_radar(index); draw_outline()
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
					if pixel2 == 15: string += col_fg[15] # fix holes
					else: string += col_fg[pixel1]
					string += chr(0x2588)
				else:
					string += col_bg[pixel2]
					string += col_fg[pixel1]
					string += chr(0x2580)
		string += "\033[0;30m"
	return string

def main():
	if args.update:
		frames = 1
		if args.anim:   frames = 3
		if args.frames: frames = clamp(int(args.frames), 1, 6)
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
			for i in anim: print(i); sleep(0.5)
			sleep(1.5)
	else: print(get_str(0))

# https://github.com/amit1rrr/numcompress/
def decompress(text):
	result = []
	index,last_num = 0,0
	while index < len(text):
		index, diff = decompress_number(text, index)
		last_num += diff
		result.append(last_num)
	return result
def decompress_number(text, index):
	result,shift = 1,0
	while True:
		b = ord(text[index]) - 64
		index += 1
		result += b << shift
		shift += 5
		if b < 0x1f: break
	return index, (~result >> 1) if (result & 1) != 0 else (result >> 1)

# Map outlines, encoded to save space
lx = ("oG`@?CCH?KN@LB@_@k@GD?LCGF@GEEEF?EBD?@HCCEGE@GLCFDeFkEgE}DqDeB?MCIGAOAKAQMBICCIEMYC[CMr@n@OUMAFGMOISEGAGCE@KBGOKOKYUS@e@DM^@^BXNCFF@VNCQGJCHAHE@EGMKMIBH"
"E@I@G?ACCIBE@G?IIH?GGIGEIQ?ED@E?H?JBMCIMGIABDBDH@HMECAACLCKEOKQ_@i@SEBAF?c@QEGO?AGKEABAGJW@e@eCEGGC?G@M@GB?A?AEA]G?EYQ?MABA?CEEDAEAJB@D?HFHHH@D?BJDJFHCF?N@AEJ"
"BACIBEAII?AARH?LFBBABA?BJJ\\@FBPDB?AB@CD@DAI@B@DBABAD@AFFAADDFD?@EKJFA?E?C?EC?B@E?@AB@DRCD?DHAGH?E@@BACABK@ADAFB@DEDGH@AGCPHHGJM]@^a@?DADJMGBJTSIE?MABIF?FCTDA"
"Y?CEC@DFNBAPU?HEFJKKEFTHBALD@@@JHNFBCFDB?FBARHGF@?DACDADCDB?DBABDC?BCCGSDADEMMBDBABDDDH@AEAFFNB?DGH@A@C?FBEDH@B?K@@?@@B@C?HC@G?@A?B@HNAFBNPGd@LELCXKPBL?FBDAHF"
"DDH`@NVFKO?IELIOBX@NGDHJRDJTGHb@X@E@D?AHL@HC@DDCF?`@HFAJIHDADDDGDDHGEFBBB?K@B?CA?G@BJTDHFHFD?BCFHFFL@\\ZDDHPr@JCF@VPJDD`A?pBtCA|A@D?ADTJ@DADHP@JDLL@DA@A@?HABB"
"BD@B@BJ@CADDJ?B?C?KJE]\\F@RACPPADCJJ@EAC@CBBAF@A?DE?E@CCBCCBAA@AAABEBAAB@CBEA?CS,ur@G?Q@KTL,ar@SE\\C,et@EKP,qv@ADC,ux@GEFD,alAEFBE,ikAE,skAA,skA?,ykAC,}iABB?C"
"AA,siAIAJ,}hAKBF,ihAAAB,mhAC@@,yhAG,aeAB?CE?IKCSGFCAFBf@B@,}fAUH@JA,}gAA,_gAC,_gAA,gcAG,mbA?,kbAA,ybAC,qbAA,sbACK@RD,s|@ABA,w|@@A,}q@A,cr@?,gr@E@,qr@K,wq@G,}q"
"@@,as@I,ms@G,mn@GEFD,qj@M,_k@I,_i@O,}h@LFHD?EC,}g@EB@,_LE,gME,gMCAEF,qKIEDF@,oK@FCE,aKB,sGA,{GE@B,qGE?D?,wGEB@,{G@EB,eH@AA@,kHCAD@@BCABBCCA,qHFAA@,kHBAA?,kHC@"
"?@?,aHA,aHC,_p@E,cp@E,mp@?,oGIECQOUE}@WsA,eO?E@EICVHMBA,uVnO,oK?}BwA,}RgEwGgH,eY??,}a@fJ?wG,m_@?,}R?DNDEAQP?FAG@F,mP?KCc@ODCDCGIU?KIGKCa@?AM,i\\DoCAyB?OGG]KII"
"UEUk@_@Q?EAKBB@,w`@?,}a@?,}a@kG,m_@}EQEWEOCGCGAEA?CCGEICEJIAG?G@,}g@C?KA?G?JEGC?,m_@iH,ko@rE?A?@?CA@DCC,kp@ICg@KKO?K@G?,kn@F?PD?GDIGCEKGMA?EBEMAG?I?BBX@ED@H?B"
"@EKAICECKHC]?A@?EC?E@ADBBBABCDABABCJAFAHAF?B@D?FCF?DCBC@CBCBCBID?HBBAB@ABmABCE,}k@qB,ek@qDC?JY,wi@qBo@I,ep@oB,}t@oA?,mw@u@,}q@GSCBQ@ACC@GCAQKGIMGCK@Y@EECEEGKE"
"KKCGAIAC@GCE@ECEASGA@E?,ms@@C?KEDE?,ejAA,mjAB,qjAB,_iAFB,ahA?BABLBJ@@@C,weA???A?BA@CA?mAEAAEC,ihA@P?@,keA@G@C@I,seAY?A?g@,w}@?qDGEGADHAB?CAKN?,adA_@,y|@?}DEG,"
"wbAAY,c~@?OCGCI?ECGEC@K@CEEC?FD,ez@?KMCIIEMAOG@IGEEIKCEAICSC,_{@\\?D?F@Vv@d@Pr@@FAx@,qp@uA?y@k@s@o@,}x@aAAI?_AaD,ax@AGGMQCACGAEGEECC?A,g_Aj@@h@@BB@t@ZF@MECAE?"
"ACGAEC?EI?CAEC?AAC,gs@AANC,et@?AHAeB,mv@OEC?AB@@CBEAAiBACA@ACIE")
ly = ("_JBNMPADB?LVNBIAGIBO?@A@F?HCAG?IBGFIABAFATFPDBJ??????NCUC@AAC?B?CAAGB@GCDC?C?Q_@CFDEKBABD?D?BDECIFGFCKAAHADK?KG?GJG?MJ?IJ]SELEKIKGQUQGMCFLRTPDJJL@D?BAHQ"
"HKLFB@BBD?E@G?EEE@CESAGCIGFHBEa@CQDAKAKICC?@A?AA?ADAHHNL@FB@DDCCBAAB@D?FD@@DJBR?H?BEF?DDBB@D?BD@J\\AECFKu@CCACAG@GCA@CE@C@EBIFKBFCEK@GCDGCAEKGGAEEC@GCAEA@D?K?"
"EHIH?BE?AECA?CBG?EE?BFFAKK?GAAM?MCAAAC?AAIABD??DDB@DBAECEGECAE?CAA?EAAC?IAD@DAHB@BBAB@CFAD@J?B?EE@E@CMQDDICIFHAHKAQITYGBE?HMAEHBGI?BAGGQFCBECHM@MHBIGBI@@CDIC?"
"AEFKDCI?CDGGEKJK@AKMBEG@ACC@EG@EEDCHKACBEAE@CCMCCQ?E@EQU_@?B@QYc@c@GGEE@C@CBDE@BPDFJ@FGFD@@@A@G@ND@BHD?E@D@EAEDHBJH@?BBD@LD@FDCCIP?HGH?DE?FAGAFI?RQBAEFIEDGBIE"
"IGILF@EKHIFFH?ECJCBBDAGE@GBADBEBOEGM?BEDKEDIA@C?KB?CCM@CFI?I?G?IAOGAF@B@D@NFFBDFDJDXFX?BC?a@VPFFFNNBH@?Q?l@HGD?D?NNDA@@F?BDDABAB?D@BBH@BD?F?BBD?HJ@FDAHFDH?EEP"
"DA@BMFDCRNBJHPFDH@JBJL?FBJDBHHFB?H@A\\?@D?@NJ@@?BB?BF@FACDA?,sHCGN@??E,}GFDIC,qKCPM,oJE?D,eJBG?B,eLCEDB,sLA,uL@,oL@,oL?,gOB?A@E@,aP?CB,aP@BE,{O?DE,{O@DG,}OB,_"
"Q?@D?@BA@@BG?AA?GBC,uPHC@CC,gP?,iP?,kP?,kTJ,gTA,_T?,_UF,cUE,}USQQEC,k`@JAI,a`@IG,}^@,{^@,u^FF,}]A,e^B,e^@,}]?,}]?,w^@G@B,k_@H,__@B,g`@F,k`@EEOMMUK,ic@?DE,cZA,"
"mZG,}Y?CAD,cYA?A?B,gY@ACB,eY?,oF?,yFAAB,}FCA@B,}F?BC,_GCAD,aG?E@B,wGA@BAF?B?@ECE?,sGBB?C,gH@BAC,kHCA@AD,}FA,yFA,gIB,aI@,}H@,aJ?EMAD?CJB?,mFiBGCGCEc@QAQgA,gO@,"
"gOuB{AcA,oU???,q\\`F~C,oP?`D?,oF_I,gOeFGBE]QSMOEMAIA,oFe@KK[AWGEECHYEEMBAB?D@K,_\\F?rD?kAG@GE@KDIFGFKC}@EIOQGS,cVR,oP_D,wQ?,_N?GB?CCE?MIMEKOECIIC@ICGEAkBk@eA,"
"oFIUU[KKSGGACgA,iJ?,kM?AAC?A?CCKAE,oICEEE?CCCM?I,iICUGGCEYEACAICEQCAEQCECCGIAGEGGGECG?KMGCEMABEUCUCCE?GCBCECE@GBEAC?CEC?ACGEIEACC?M?CECAGCCACCGEAG?CKGCGICCC?I"
"A?KEM,oZ?,cV?CCK?,_Q?@I,qNA,oO?kB,sO@,oUHEBDFDB?@BAADGFELGJ?JD@J@A@CGAE@ABECA?D?FHEBBF?BAJVDF@t@,oTBHBHJLH|A,uLK,uLK,uLI,{MLjA,oKCEEECOOSCCC,mKEAGEIEKG@Aa@AB@"
"?@?,qOJ?WC,oPDBB\\?X,cOA????,{NK?EMAAEICCG?EIGC,_PM,}Pc@?B?,aRq@A,aRUJAFC?B?@C?I?CCAACAGAI,uSKQEGEDCBB?F@JJJCANAD?HHKF,yTOCACACE@?@A@?G?,_X??????,}UA@A?A?,_XH"
"@FBF?D?BCBBAF@?@F,kYb@?@BDAB@GGCGAEEEA?AECCCCGCCGECGEA?A,_XAAwB{@,u]BDDD?,_XqAMECACGEKMGI?GE?F@D@C?")
lines_x,lines_y = [],[]
for f in lx.split(","): lines_x.append(decompress(f))
for f in ly.split(","): lines_y.append(decompress(f))
main()