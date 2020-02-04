#!/usr/bin/env python3

from PIL import Image, ImageEnhance
import glob, os
import shutil
import yaml
import argparse


TEXTURE_VARIANTS = (
	'diffuse',
	'norm',
	'bump',
	'gloss',
	'glow',
	'pants',
	'shirt',
)

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
parser.add_argument('-i', '--input',  default="textures", type=str, help='Directory containing the variant textures')
parser.add_argument('-t', '--type', default='all', type=str, help="Comma-separated list of texture variants to build. Defaults to `all` which builds all variants available.")
parser.add_argument('-o', '--output', default="~/.darkplaces/id1/textures", type=str, help='Quake textures directory to put the bump map images.')
parser.add_argument('-f', '--format', default='tga', type=str, help='Image format to use. (TODO)')
args = parser.parse_args()


if args.type == 'all':
	# args.type = TEXTURE_VARIANTS
	# temp override
	args.type = ('diffuse', 'bump','gloss','glow')
else:
	args.type = args.type.split(',')

t_defs = {}
for variant in args.type:
	try:
		t_defs[variant] = yaml.load(open(os.path.abspath(os.path.expanduser(variant + '.yml')), 'r'))
	except FileNotFoundError:
		t_defs[variant] = {}

# Set abolute paths for input and output directories
args.input  = os.path.abspath(os.path.expanduser(args.input))
args.output = os.path.abspath(os.path.expanduser(args.output))

# Check that the output directory exists
if not os.path.isdir(args.output):
	raise NotADirectoryError("The output directory `{}` does not exist".format(args.output))

# Loop over the diffuse textures
for t_path in glob.glob(os.path.join(args.output, '*.tga')):
	if not any('_' + tv in t_path for tv in TEXTURE_VARIANTS):
		for variant in args.type:
			t_filename = os.path.basename(t_path) # window01_4.tga
			t_name, t_ext = os.path.splitext(t_filename) # (window01_4, .tga)
			t_format = t_ext[1:] # tga
			im = None

			if variant != 'diffuse':
				dst_filename = t_name + '_' + variant + t_ext
			else:
				dst_filename = t_name + t_ext

			dst = os.path.abspath(os.path.join(args.output, dst_filename))

			if variant in t_defs and  t_name in t_defs[variant]:
				# If variant definition use that
				layers = t_defs[variant][t_name]

				# We only want to scale texture brightness based regular layers
				# anything prefixed with __ is a special layer that isn't scaled
				num_layers = 1
				if len(layers) > 1:
					num_layers = len([l for l in layers if l == None or l[:2] != '__'])

				for layer_level, layer_name in enumerate(layers):
					if layer_name:
						if DEBUG:
							print('Layer: ', layer_name)

						layer_filename = layer_name
						if layer_name[:2] == '__':
							layer_filename = layer_name[2:]

						layer = Image.open(os.path.join(args.input, variant, '{}{}'.format(layer_filename, t_ext)))

						if layer.mode is not 'RGBA':
							layer = layer.convert('RGBA')

						if im is None:
							im = Image.new( 'RGBA', (layer.size[0], layer.size[1]), "black")

						if layer_name[:2] != '__':
							layer_min = float(layer_level) / num_layers
							layer_max = float(layer_level + 1) / num_layers
							scale_layer(layer, layer_min, layer_max)

						im = Image.alpha_composite(im, layer)

				print("Creating", dst)
				im.save(dst, args.format)
			else:
				# There is no texture definition
				# if variant file exists, copy it over
				try:
					src = os.path.abspath(os.path.join(args.input, variant, t_filename))
					print('Copying {} to {}'.format(src, dst))
					shutil.copy(src, dst)
				except FileNotFoundError:
					if variant == 'gloss':
						# open the diffuse texture
						diffuse_texture = Image.open(t_path)
						# create new black image of dimensions
						im = Image.new('RGBA', diffuse_texture.size, (0, 0, 0, 255))
						# save new image as gloss texture
						im.save(dst, args.format)
					elif variant == 'bump':
						# open the diffuse texture
						diffuse_texture = Image.open(t_path)
						# create new black image of dimensions
						im = Image.new('RGBA', diffuse_texture.size, (128, 128, 128, 255))
						# save new image as gloss texture
						im.save(dst, args.format)
					else:
						print('No {} file found for {}'.format(variant, t_name))
