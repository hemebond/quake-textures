import os
import shutil
from argparse import ArgumentParser, Action, RawDescriptionHelpFormatter
from pathlib import Path
import logging
import tracemalloc
from typing import Union, TextIO, IO
from copy import copy

import yaml
from PIL import Image, ImageChops, ImageFilter, ImageOps
from gimpformats.gimpXcfDocument import GimpDocument, flattenAll
from gimpformats.GimpLayer import GimpLayer

import normal
import numpy as np
import cv2



logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)



class Document(GimpDocument):
	def __init__(self, filename):
		self.stat = os.stat(filename)

		# gimpformats requires an explicit string otherwise it falls back to BytesIO
		super().__init__(str(filename))

		self.layer_tree = self.get_layers_as_tree()
		apply_masks(self.layer_tree)

	def get_layers_as_tree(self):
		layer_tree = {
			'children': [],
		}
		for idx, layer in enumerate(self.layers):
			parent = layer_tree

			if layer.itemPath:
				layer.itemPath.pop()

				parent = layer_tree
				for level_idx in layer.itemPath:
					parent = parent['children'][level_idx]

			if layer.isGroup:
				parent['children'].append({
					'layer': layer,
					'children': [],
				})
			else:
				parent['children'].append(layer)

		return layer_tree



DOCUMENT_CACHE = {}  # maintain a cache of opened GimpDocuments



VARIANT_TYPES = (
	'diffuse',
	'norm',
	'bump',
	'gloss',
	'glow',
	'pants',
	'shirt',
)
TEXTURE_VARIANTS = VARIANT_TYPES



def get_document(name: str, cache: dict = DOCUMENT_CACHE) -> Document:
	if name in cache:
		return cache[name]

	filepath = os.path.join('src', name + '.xcf')
	document = Document(filepath)
	apply_masks(document.layer_tree)
	cache[name] = document
	return document



def get_layer(document: GimpDocument, name: str) -> Union[GimpLayer, None]:
	for layer in document.layers:
		if layer.name == name:
			return layer

	return None



def get_layer_tree(document: GimpDocument):
	layer_tree = {
		'children': [],
	}
	for idx, layer in enumerate(document.layers):
		parent = layer_tree

		if layer.itemPath:
			layer.itemPath.pop()

			parent = layer_tree
			for level_idx in layer.itemPath:
				parent = parent['children'][level_idx]

		if layer.isGroup:
			parent['children'].append({
				'layer': layer,
				'children': [],
			})
		else:
			parent['children'].append(layer)

	return layer_tree




def apply_masks(group: dict, parent_mask: Image = None):
	group_mask = None

	if 'layer' in group:
		group_mask = getattr(group['layer'], 'mask')

	if parent_mask is None:
		mask = getattr(group_mask, 'image', None)
	else:
		if group_mask is None:
			mask = parent_mask
		else:
			mask = ImageChops.multiply(
				parent_mask,
				group_mask,
			)

	for layerOrGroup in group.get('children', []):
		if isinstance(layerOrGroup, dict) and 'children' in layerOrGroup:
			apply_masks(layerOrGroup, mask)
		else:
			if layerOrGroup.mask is not None:
				layerOrGroup.image.putalpha(
					layerOrGroup.mask.image
				)

			if mask is not None:
				if layerOrGroup.image.mode == 'RGB':
					layerOrGroup.image.putalpha(
						mask
					)
				else:
					layerOrGroup.image.putalpha(
						ImageChops.multiply(
							mask,
							layerOrGroup.image.getchannel('A'),
						)
					)

	if 'layer' in group:
		group['layer'].visible = False




def make_norm_texture(bump_image: Image) -> Image:
	bump_scaled = bump_image.resize((bump_image.width * 2, bump_image.height * 2), Image.Resampling.LANCZOS)

	# we need to invert the height map because the algorithm we're using creates an inverted normal map
	bump_scaled = ImageChops.invert(bump_scaled)

	# Convert the image to a 1-dimensional numpy array
	numpy_image = np.array(bump_scaled)
	rows, cols = numpy_image.shape

	x, y = np.meshgrid(np.arange(cols), np.arange(rows))
	x = x.astype(np.float32)
	y = y.astype(np.float32)

	# Calculate the partial derivatives of depth with respect to x and y
	dx = cv2.Sobel(numpy_image, cv2.CV_32F, 1, 0)
	dy = cv2.Sobel(numpy_image, cv2.CV_32F, 0, 1)

	# Compute the normal vector for each pixel
	normal = np.dstack((-dx, -dy, np.ones((rows, cols))))
	norm = np.sqrt(np.sum(normal**2, axis=2, keepdims=True))
	normal = np.divide(normal, norm, out=np.zeros_like(normal), where=norm != 0)

	# Map the normal vectors to the [0, 255] range and convert to uint8
	normal = (normal + 1) * 127.5
	normal = normal.clip(0, 255).astype(np.uint8)

	# Save the normal map to a file
	normal_bgr = cv2.cvtColor(normal, cv2.COLOR_RGB2BGR)
	im = Image.fromarray(normal)
	im.putalpha(bump_scaled)
	return im



class Texture:
	def __init__(self, name, document, definition):
		self.name = name
		self.document = document
		self.definition = definition
		self.width = document.width
		self.height = document.height

		apply_masks(self.document.layer_tree)

	def render(self) -> dict:
		variants = {}

		for variant_name, variant_definition in [
			(k, v)
			for k, v
			in self.definition.items()
			if k in TEXTURE_VARIANTS
		]:
			variants[variant_name] = TextureVariant(self.document, variant_definition).render()

			if variant_name == 'bump':
				# FTEQW refuses to load bump textures that are not grayscale
				variants[variant_name] = ImageOps.grayscale(variants[variant_name])

				# Create a normal map texture from the bump map
				log.debug("Creating norm texture")
				variants['norm'] = make_norm_texture(variants['bump'])
				log.info(variants['norm'])

		if 'bump' not in variants:
			variants['bump'] = self.default_bump()

		if 'gloss' not in variants:
			variants['gloss'] = self.default_gloss()

		return variants

	def has_variant(self, variant_type) -> bool:
		if variant_type in self.variants:
			return True

		return False

	def default_gloss(self) -> Image:
		# create new black image
		return Image.new(
			'RGBA',
			(self.width, self.height),
			(0, 0, 0, 255),
		)

	def default_bump(self) -> Image:
		# create new grey image
		return Image.new(
			'RGBA',
			(self.width, self.height),
			(128, 128, 128, 255),
		)



class TextureVariant:
	def __init__(self, document, definition):
		self.document = document
		self.definition = definition
		self.width = document.width
		self.height = document.height

	def render(self) -> Image:
		document = copy(self.document)

		for layer in document.layers:
			if layer.name == 'Background' or layer.name in self.definition:
				layer.visible = True
			else:
				layer.visible = False

		return flattenAll(
			document,
			(
				self.width,
				self.height,
			)
		)



def new_render_textures(source_directory: Path, definitions: dict):
	document_cache = DocumentCache(source_directory)
	textures = {}

	for name, definition in definitions.items():
		xcf_document_name = definition['src']
		xcf_document = document_cache.get(xcf_document_name)
		textures[name] = Texture(name, xcf_document, definition).render()

	return textures



class DocumentCache:
	def __init__(self, source_directory: Path):
		self.source_directory = source_directory
		self.cache = {}

	def _make_filepath(self, name: str) -> Path:
		log.debug(Path(self.source_directory, f"{name}.xcf"))
		return Path(self.source_directory, f"{name}.xcf")

	def get(self, name: str) -> Document:
		if name in self.cache:
			return self.cache[name]
		log.debug(f"name: {name}")
		filepath = self._make_filepath(name)
		log.debug(f"filepath: {filepath}")
		document = Document(filepath)

		# log.debug(dir(document))
		self.cache[name] = document

		return document




class TextureBuilder:
	def __init__(
		self,
		texture_definitions: dict,
		source_directory: Path,
	):
		self.texture_definitions = texture_definitions
		self.cache = DocumentCache(source_directory)

	def save(self, destination_directory: Path, extension: str = "tga"):
		for name, definition in self.texture_definitions.items():
			xcf_document_name = definition['src']
			xcf_document = self.cache.get(xcf_document_name)

			diffuse_filepath = self.get_variant_filepath(
				name,
				'diffuse',
				extension,
				destination_directory,
			)

			try:
				diffuse_mtime = os.stat(diffuse_filepath).st_mtime

				# If the source file hasn't changed, don't re-render
				if diffuse_mtime > xcf_document.stat.st_mtime:
					log.debug(f"Skipping {diffuse_filepath}")
					continue
			except FileNotFoundError:
				pass

			texture = Texture(name, xcf_document, definition).render()

			for variant_type, variant_image in texture.items():
				variant_filepath = self.get_variant_filepath(
					name,
					variant_type,
					extension,
					destination_directory,
				)

				try:
					os.mkdir(variant_filepath.parent)
				except FileExistsError:
					pass

				log.info(f"Saving {variant_filepath.resolve()}")
				log.info(variant_image)

				if str(variant_filepath)[-3:] == "jpg":
					if variant_image.mode == 'RGBA':
						log.info("Converting to RGB")
						variant_image = variant_image.convert('RGB')

					variant_image.save(variant_filepath.resolve(), quality=100, optimize=True)
				else:
					variant_image.save(variant_filepath.resolve())

	def get_variant_filepath(self, name, variant_type, extension, destination_directory):
		if variant_type == 'diffuse':
			if name.startswith("{"):
				filename = f"{name}.tga"
			else:
				filename = f"{name}.{extension}"
		elif variant_type == 'norm':
			filename = f"{name}_norm.tga"
		else:
			filename = f"{name}_{variant_type}.{extension}"

		return destination_directory.joinpath(filename)




class ResolvePathAction(Action):
	def __call__(self, parser, namespace, values, option_string=None):
		values = values.expanduser().resolve()
		setattr(namespace, self.dest, values)



class LogLevelMapperAction(Action):
	def __call__(self, parser, namespace, values, option_string=None):
		values = logging._nameToLevel[values.upper()]
		setattr(namespace, self.dest, values)



if __name__ == "__main__":
	parser = ArgumentParser(
		description="Generate texture variants, from a set of definitions, directly from XCF files.",
		epilog='''Example: python $(prog) xcftotexture.yml ~/.darkplaces/id1_tex/textures/''',
		formatter_class=RawDescriptionHelpFormatter,
	)
	parser.add_argument(
		"infile",
		type=Path,
		action=ResolvePathAction,
		help="Texture definition YAML file"
	)
	parser.add_argument(
		"outdir",
		type=Path,
		action=ResolvePathAction,
		help="Output directory"
	)
	parser.add_argument(
		"-s",
		"--src",
		default="src",
		type=Path,
		action=ResolvePathAction,
		help="Directory containing the XCF source images (DEFAULT: src)"
	)
	parser.add_argument(
		"-v",
		"--variants",
		default="all",
		type=str,
		help="Comma-separated list of texture variants to build (DEFAULT: all)"
	)
	parser.add_argument(
		"-f",
		"--format",
		default="jpg",
		type=str,
		help="Image format to use. (TODO)"
	)
	parser.add_argument(
		"-l",
		"--log-level",
		default=logging.INFO,
		action=LogLevelMapperAction,
		help="Log level"
	)
	args = parser.parse_args()

	log.setLevel(args.log_level)

	tracemalloc.start()

	with open(args.infile, 'r') as yaml_file:
		texture_defs = yaml.safe_load(yaml_file)

	texture_builder = TextureBuilder(texture_defs, args.src)
	texture_builder.save(args.outdir, extension=args.format)

	current, peak = tracemalloc.get_traced_memory()
	tracemalloc.stop()

	print(f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
