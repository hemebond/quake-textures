import os
import shutil
from argparse import ArgumentParser, Action
from pathlib import Path
import logging
import tracemalloc
from typing import Union, TextIO, IO
from copy import copy

import yaml
from PIL import Image, ImageChops
from gimpformats.gimpXcfDocument import GimpDocument, flattenAll
from gimpformats.GimpLayer import GimpLayer



logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)



class Document(GimpDocument):
	def __init__(self, filename):
		self.stat = os.stat(filename)

		# gimpformats requires an explicit string otherwise it falls back to BytesIO
		super().__init__(str(filename))

		self.layer_tree = get_layer_tree(self)



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



def render_textures(textures: dict, output_dir: str):
	for texture_name, texture_def in textures.items():
		document = get_document(texture_def['src'])

		for variant_name in TEXTURE_VARIANTS:
			layers = texture_def.get(variant_name, [])

			if layers:
				image = render_texture(
					document,
					layers,
				)

				if variant_name == 'diffuse':
					filename = "%s.tga" % texture_name
				else:
					filename = "%s_%s.tga" % (texture_name, variant_name)

				filepath = Path(os.path.join(output_dir, filename))

				if not filepath.parent.exists():
					os.mkdir(filepath.parent)

				log.info("Save to %s" % filepath)

				image.save(filepath)



class Texture:
	def __init__(self, name, document, definition):
		self.name = name
		self.document = document
		self.definition = definition
		self.width = document.width
		self.height = document.height

	def render(self) -> dict:
		variants = {}

		for variant_name, variant_definition in [
			(k, v)
			for k, v
			in self.definition.items()
			if k in TEXTURE_VARIANTS
		]:
			variants[variant_name] = TextureVariant(self.document, variant_definition).render()

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

	def get(self, name: str) -> dict:
		if name in self.cache:
			return self.cache[name]

		filepath = self._make_filepath(name)

		document = Document(filepath)

		log.debug(dir(document))
		self.cache[name] = document

		return self.cache[name]



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

			texture = Texture(name, xcf_document, definition).render()

			for variant_type, variant_image in texture.items():
				if variant_type == 'diffuse':
					filename = f"{name}.{extension}"
				else:
					filename = f"{name}_{variant_type}.{extension}"

				variant_filepath = destination_directory.joinpath(filename)

				if not variant_filepath.parent.exists():
					os.mkdir(variant_filepath.parent)

				log.info(f"Saving {variant_filepath.resolve()}")
				variant_image.save(variant_filepath.resolve())



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
		description="Generate texture variants from a set of definitions."
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
		default="tga",
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
	texture_builder.save(args.outdir)

	current, peak = tracemalloc.get_traced_memory()
	tracemalloc.stop()

	print(f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
