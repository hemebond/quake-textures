import os
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
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.layer_tree = get_layer_tree(self)



DOCUMENT_CACHE = {}  # maintain a cache of opened GimpDocuments



TEXTURE_VARIANTS = (
	'diffuse',
	'norm',
	'bump',
	'gloss',
	'glow',
	'pants',
	'shirt',
)



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



def update_visible_layers(document: GimpDocument, layers: list[str]):
	for layer in document.layers:
		if layer.name == 'Background' or layer.name in layers:
			layer.visible = True
		else:
			layer.visible = False



def render_texture(document: Document, layers: list[str]):
	update_visible_layers(document, layers)
	return flattenAll(document, (document.width, document.height))



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

				print("Save to %s" % filepath)

				image.save(filepath)



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
		# gimpformats requires an explicit string otherwise it falls back to BytesIO
		document = GimpDocument(str(filepath))
		mtime = os.stat(filepath).st_mtime

		self.cache[name] = {
			'path': filepath,
			'document': document,
			'mtime': mtime,
		}

		return self.cache[name]

	def get_document(self, name) -> GimpDocument:
		return self.get(name)['document']

	def get_mtime(self, name) -> float:
		return self.get(name)['mtime']



class TextureBuilder:
	def __init__(self):
		pass



class Texture:
	def __init__(self, definition: dict):
		pass

	def render_variant(self):
		pass

	def save(self):
		pass




class TextureVariant:
	def __init__(self, name: str, type: str, document: GimpDocument, definition: dict):
		pass

	def render(self, document: GimpDocument, layers: list):
		pass

	def save(self, output_directory: Path):
		pass



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
	render_textures(texture_defs, args.outdir)

	current, peak = tracemalloc.get_traced_memory()
	tracemalloc.stop()

	print(f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")


