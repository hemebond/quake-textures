#!/usr/bin/env python3

from PIL import Image, ImageEnhance
import glob, os
import shutil
import yaml

IMG_TYPE = 'tga'
IMG_FORMAT = 'tga'
OUTPUT_PATH = '/home/james/.darkplaces/id1tex/textures'
BUMP_PATH = 'textures/bump'
DEBUG = False

TEXTURE_VARIANTS = [
	'norm',
	'bump',
	'gloss',
	'glow',
	'luma',
	'pants',
	'shirt',
]

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


texture_definitions = yaml.load(open('images.yml', 'r'))


# loop over the diffuse textures
for t_path in glob.glob(OUTPUT_PATH + '/*.tga'):
	if not any('_' + tv in t_path for tv in TEXTURE_VARIANTS):
		t_filename = os.path.basename(t_path) # window01_4.tga
		t_name, t_ext = os.path.splitext(t_filename) # (window01_4, .tga)
		t_format = t_ext[1:] # tga
		im = None

		dst = os.path.abspath(OUTPUT_PATH + '/' + t_name + '_bump' + t_ext)

		try:
			# If bump definition use that
			bump_layers = texture_definitions[t_name]['bump']
			for layer_level, layer_filename in enumerate(bump_layers):
				if layer_filename:
					if DEBUG:
						print('Layer: ', layer_filename)

					layer = Image.open('{}/{}{}'.format(BUMP_PATH, layer_filename, t_ext))

					if layer.mode is not 'RGBA':
						layer = layer.convert('RGBA')

					if im is None:
						im = Image.new( 'RGBA', (layer.size[0], layer.size[1]), "black")

					layer_min = float(layer_level) / len(bump_layers)
					layer_max = float(layer_level + 1) / len(bump_layers)
					scale_layer(layer, layer_min, layer_max)

					im = Image.alpha_composite(im, layer)

			print("Save {} {}".format(dst, IMG_TYPE))
			if not DEBUG:
				im.save(dst, IMG_TYPE)
		except KeyError:
			# There is no texture definition so
			# if bump file exists, copy it over
			try:
				src = BUMP_PATH + '/' + t_filename
				print('Copy {} to {}'.format(src, dst))
				if not DEBUG:
					shutil.copy(src, dst)
			except FileNotFoundError:
				print('No bump file found for {}'.format(t_name))

exit()

for name, config in texture_definitions.items():
	im = None

	if 'bump' in config:
		layers = config['bump']

		if len(layers) > 1:
			for level, filename in enumerate(layers):
				if filename:
					layer = Image.open('{}/{}.{}'.format(BUMP_PATH, filename, IMG_TYPE))

					if im is None:
						im = Image.new( 'RGBA', (layer.size[0], layer.size[1]), "black")

					layer_min = float(level) / len(layers)
					layer_max = float(level + 1) / len(layers)
					scale_layer(layer, layer_min, layer_max)

					im = Image.alpha_composite(im, layer)
		else:
			im = Image.open('{}/{}.{}'.format(BUMP_PATH, layers[0], IMG_TYPE))

		im.save(os.path.abspath('{}/{}_bump.{}'.format(OUTPUT_PATH, name, IMG_TYPE)), IMG_TYPE)
