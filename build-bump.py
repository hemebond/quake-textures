#!/usr/bin/env python3

from PIL import Image, ImageEnhance
import glob, os
import shutil
import yaml
import argparse


TEXTURE_VARIANTS = [
	'norm',
	'bump',
	'gloss',
	'glow',
	'luma',
	'pants',
	'shirt',
]

DEBUG = False

def scale_pixel(pixel, minimum, maximum):
	delta = maximum - minimum

	# if DEBUG:
	# 	print(pixel, minimum, maximum, delta, sep=', ')

	def scale(pixel_value):
		return int(((pixel_value / 255) * delta + minimum) * 255)

	try:
		r = scale(pixel[0])
		g = scale(pixel[1])
		b = scale(pixel[2])

		return (r, g, b, pixel[3])
	except TypeError:
		# This is not RGBA pixel so we  will return an RGBA pixel
		return scale(pixel)



def scale_layer(im, minimum, maximum):
	pixels = im.load()

	# if DEBUG:
	# 	print(im, minimum, maximum)

	for i in range(im.size[0]):
		for j in range(im.size[1]):
			px = pixels[i, j]
			pixels[i,j] = scale_pixel(px, minimum, maximum)


parser = argparse.ArgumentParser(description='Build bump map images for Quake textures.')
parser.add_argument('-i', '--input',  default="textures/bump", type=str, help='Directory containing the bump map images')
parser.add_argument('-c', '--config', default='textures.yml', type=open, help="YAML file containing definitions for textures.")
parser.add_argument('-o', '--output', default="~/.darkplaces/id1/textures", type=str, help='Quake textures directory to put the bump map images.')
parser.add_argument('-f', '--format', default='tga', type=str, help='Image format to use. (TODO)')
args = parser.parse_args()


texture_definitions = yaml.load(args.config)
args.config.close()

if '~' in args.input:
	args.input = os.path.expanduser(args.input)
args.input = os.path.abspath(args.input)
print(args.input)

if '~' in args.output:
	args.output = os.path.expanduser(args.output)
args.output = os.path.abspath(args.output)

print(args.output)
if not os.path.isdir(args.output):
	raise NotADirectoryError("The output directory `{}` does not exist".format(args.output))

# loop over the diffuse textures
for t_path in glob.glob(os.path.join(args.output, '*.tga')):
	if not any('_' + tv in t_path for tv in TEXTURE_VARIANTS):
		t_filename = os.path.basename(t_path) # window01_4.tga
		t_name, t_ext = os.path.splitext(t_filename) # (window01_4, .tga)
		t_format = t_ext[1:] # tga
		im = None

		dst_filename = t_name + '_bump' + t_ext
		dst = os.path.abspath(os.path.join(args.output, dst_filename))

		try:
			# If bump definition use that
			bump_layers = texture_definitions[t_name]['bump']
			for layer_level, layer_filename in enumerate(bump_layers):
				if layer_filename:
					if DEBUG:
						print('Layer: ', layer_filename)

					layer = Image.open(os.path.join(args.input, '{}{}'.format(layer_filename, t_ext)))

					if layer.mode is not 'RGBA':
						layer = layer.convert('RGBA')

					if im is None:
						im = Image.new( 'RGBA', (layer.size[0], layer.size[1]), "black")

					layer_min = float(layer_level) / len(bump_layers)
					layer_max = float(layer_level + 1) / len(bump_layers)
					scale_layer(layer, layer_min, layer_max)

					im = Image.alpha_composite(im, layer)

			print("Creating", dst)
			if not DEBUG:
				im.save(dst, args.format)
		except KeyError:
			# There is no texture definition so
			# if bump file exists, copy it over
			try:
				src = os.path.abspath(os.path.join(args.input, t_filename))
				print('Copying {} to {}'.format(src, dst))
				if not DEBUG:
					shutil.copy(src, dst)
			except FileNotFoundError:
				print('No bump file found for {}'.format(t_name))
