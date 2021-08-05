import json

from PIL import Image, ImageChops

from gimpformats.gimpXcfDocument import GimpDocument, flattenAll
from gimpformats.GimpLayer import GimpLayer
project = GimpDocument("/home/james/Untitled.xcf")
# (flattenAll(project, (8, 8))).show()



# import layeredimage.io
# project = layeredimage.io.openLayerImage('/home/james/Untitled.xcf')
# (project.getFlattenLayers()).show()


# """List data on groups followed by the direct children of a gimp xcf document
# """
# # layers = project.layers
# # index = 0
# # print("## Group info...")
# # while index < len(layers):
# # 	layerOrGroup = layers[index]
# # 	if layerOrGroup.isGroup:
# # 		index += 1
# # 		while layers[index].itemPath is not None:
# # 			print("Group \"" + layerOrGroup.name + "\" contains Layer \"" + layers[index].name + "\"")
# # 			layers.pop(index)
# # 	else:
# # 		index += 1

# # print("## Document direct children...")
# # for layerOrGroup in layers:
# # 	print("\"" + layerOrGroup.name + "\" is a " + ("Group" if layerOrGroup.isGroup else "Layer"))

# # Toggle layer
# # layer.visible = True


# def get_layer_by_name(project, name):
# 	for layer in project.layers:
# 		if layer.name == name:
# 			return layer
# 	return None



layer_tree = {
	'children': [],
}
for idx, layer in enumerate(project.layers):
	print(idx, layer.name, layer.itemPath, type(layer), layer.imageHierarchy._levelPtrs)

	layer_idx = idx
	parent = layer_tree

	if layer.itemPath:
		layer_idx = layer.itemPath.pop()

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




def apply_masks(group, parent_mask=None):
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

apply_masks(layer_tree)
# for layer in project.layers:
# 	if hasattr(layer, 'image'):
# 		layer.image.show()

(flattenAll(project, (8, 8))).show()


# def flatten_children(group):
# 	for idx, child in enumerate(group['children']):
# 		if isinstance(child, dict) and 'children' in child:
# 			flattened_layer = flatten_children(child)
# 			group['children'][idx] = flattened_layer

# 	# print_children(group['children'])
# 	# print(group['children'])

# 	flattened_image = flattenAll(group['children'], (8, 8))
# 	if 'layer' in group:
# 		group_layer = group['layer']

# 		if group_layer.mask is not None:
# 			flattened_image.show()
# 			flattened_image.putalpha(group_layer.mask.image)

# 		flattened_image.show()

# 		new_layer = GimpLayer(
# 			parent=group_layer.parent,
# 			name=group_layer.name,
# 			image=flattened_image,
# 		)
# 		return new_layer
# 	else:
# 		return flattened_image



# (flatten_children(layer_tree)).show()
