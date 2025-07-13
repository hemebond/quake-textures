#!/usr/bin/env python3
"""Gets packed pixels from a gimp image.

This represents a single level in an imageHierarchy
"""
from __future__ import annotations

import math
import zlib

import PIL.Image
from PIL.Image import Image

from .GimpIOBase import IO, GimpIOBase

# pylint:disable=invalid-name


class GimpImageLevel(GimpIOBase):
	"""Gets packed pixels from a gimp image.

	This represents a single level in an imageHierarchy
	"""

	def __init__(self, parent):
		GimpIOBase.__init__(self, parent)
		self.width = 0
		self.height = 0
		self._tiles = None  # tile PIL images
		self._image = None

	def decode(self, data: bytes, index: int = 0):
		"""Decode a byte buffer.

		:param data: data buffer to decode
		:param index: index within the buffer to start at
		"""
		ioBuf = IO(data, index)
		# print 'Decoding image level at',ioBuf.index
		self.width = ioBuf.u32
		self.height = ioBuf.u32
		if self.width != self.parent.width or self.height != self.parent.height:
			currentSize = f"({self.width}" + f",{self.height})"
			expectedSize = f"({self.parent.width}" + f",{self.parent.height})"
			msg = " Usually this implies file corruption."
			raise RuntimeError(
				"Image data size mismatch. " + currentSize + "!=" + expectedSize + msg
			)
		self._tiles = []
		self._image = None
		for y in range(0, self.height, 64):
			for x in range(0, self.width, 64):
				ptr = self._pointerDecode(ioBuf)
				size = (min(self.width - x, 64), min(self.height - y, 64))
				totalBytes = size[0] * size[1] * self.bpp
				if self.doc.compression == 0:  # none
					data = ioBuf.data[ptr : ptr + totalBytes]
				elif self.doc.compression == 1:  # RLE
					data = self._decodeRLE(ioBuf.data, size[0] * size[1], self.bpp, ptr)
				elif self.doc.compression == 2:  # zip
					data = zlib.decompress(
						ioBuf.data[ptr : ptr + totalBytes + 24]
					)  # guess how many bytes are needed
				else:
					raise RuntimeError(f"ERR: unsupported compression mode {self.doc.compression}")
				subImage = PIL.Image.frombytes(self.mode, size, bytes(data), decoder_name="raw")
				self._tiles.append(subImage)
		_ = self._pointerDecode(ioBuf)  # list ends with nul character
		return ioBuf.index

	def encode(self):
		"""Encode this object to a byte buffer."""
		dataioBuf = IO()
		ioBuf = IO()
		ioBuf.u32 = self.width
		ioBuf.u32 = self.height
		dataIndex = ioBuf.index + self.pointerSize * (len(self.tiles) + 1)
		for tile in self.tiles:
			ioBuf.addBytes(self._pointerEncode(dataIndex + dataioBuf.index))
			data = tile.tobytes()
			if self.doc.compression == 0:  # none
				pass
			elif self.doc.compression == 1:  # RLE
				data = self._encodeRLE(data, self.bpp)
				# raise RuntimeError('RLE Compression is a work in progress!')
			elif self.doc.compression == 2:  # zip
				data = zlib.compress(data)
			else:
				raise RuntimeError(f"ERR: unsupported compression mode {self.doc.compression}")
			dataioBuf.addBytes(data)
		ioBuf.addBytes(self._pointerEncode(0))
		ioBuf.addBytes(dataioBuf.data)
		return ioBuf.data

	def _decodeRLE(self, data, pixels, bpp, index=0):
		_ = self
		"""Decode RLE encoded image data."""
		ret = [[] for chan in range(bpp)]
		for chan in range(bpp):
			n = 0
			while n < pixels:
				opcode = data[index]
				index += 1
				if 0 <= opcode <= 126:  # a short run of identical bytes
					val = data[index]
					index += 1
					for _ in range(opcode + 1):
						ret[chan].append(val)
						n += 1
				elif opcode == 127:  # A long run of identical bytes
					m = data[index]
					index += 1
					b = data[index]
					index += 1
					val = data[index]
					index += 1
					amt = m * 256 + b
					for _ in range(amt):
						ret[chan].append(val)
						n += 1
				elif opcode == 128:  # A long run of different bytes
					m = data[index]
					index += 1
					b = data[index]
					index += 1
					amt = m * 256 + b
					for _ in range(amt):
						val = data[index]
						index += 1
						ret[chan].append(val)
						n += 1
				elif 129 <= opcode <= 255:  # a short run of different bytes
					amt = 256 - opcode
					for _ in range(amt):
						val = data[index]
						index += 1
						ret[chan].append(val)
						n += 1
				else:
					print("Unreachable branch", opcode)
					raise RuntimeError()
		# flatten/weave the individual channels into one strream
		flat = bytearray()
		for i in range(pixels):
			for chan in range(bpp):
				flat.append(ret[chan][i])
		return flat

	def _encodeRLE(self, data, bpp):
		"""Encode image to RLE image data."""
		_ = self

		def countSame(data, startIdx):
			"""Count how many times bytes are identical."""
			idx = startIdx
			l = len(data)
			if idx >= l:
				return 0
			c = data[idx]
			idx = startIdx + 1
			while idx < l and data[idx] == c:
				idx += 1
			return idx - startIdx

		def countDifferent(data, startIdx):
			"""Count how many times bytes are different."""
			idx = startIdx
			l = len(data)
			if idx >= l:
				return 1
			c = data[idx]
			idx = startIdx + 1
			while idx < (l - 1) and data[idx] != c:
				idx += 1
				c = data[idx]
			return idx - startIdx

		def rleEncodeChan(data):
			"""Rle encode a single channel of data."""
			ret = []
			idx = 0
			while idx < len(data):
				nRepeats = countSame(data, 0)
				if nRepeats == 1:  # different bytes
					nDifferences = countDifferent(data, 1)
					if nDifferences <= 127:  # short run of different bytes
						ret.append(129 + nRepeats - 1)
						ret.append(data[idx])
						idx += nDifferences
					else:  # long run of different bytes
						ret.append(128)
						ret.append(math.floor(nDifferences / 256.0))
						ret.append(nDifferences % 256)
						ret.append(data[idx])
						idx += nDifferences
				elif nRepeats <= 127:  # short run of same bytes
					ret.append(nRepeats - 1)
					ret.append(data[idx])
					idx += nRepeats
				else:  # long run of same bytes
					ret.append(127)
					ret.append(math.floor(nRepeats / 256.0))
					ret.append(nRepeats % 256)
					ret.append(data[idx])
					idx += nRepeats
			return ret

		# if there is only one channel, encode and return it directly
		if bpp == 1:
			return rleEncodeChan(data)
		# split into channels
		dataByChannel = []
		for chan in range(bpp):
			chanData = []
			for index in range(chan, bpp, len(data)):
				chanData.append(data[index])
			dataByChannel.append(chanData)
		# encode each channel
		for dbc in dataByChannel:  # iterate through 2d array
			dbc = rleEncodeChan(dbc)
		# join and return
		return "".join("".join(str(x)) for x in dataByChannel)

	@property
	def bpp(self):
		"""Get bpp."""
		return self.parent.bpp

	@property
	def mode(self):
		"""Get mode."""
		MODES = [None, "L", "LA", "RGB", "RGBA"]
		return MODES[self.bpp]

	@property
	def tiles(self):
		"""Get tiles."""
		if self._tiles is not None:
			return self._tiles
		if self.image is not None:
			return self._imgToTiles(self.image)
		return None

	def _imgToTiles(self, image):
		"""
		break an image into a series of tiles, each<=64x64
		"""
		ret = []
		for y in range(0, self.height, 64):
			for x in range(0, self.width, 64):
				bounds = (x, y, min(self.width - x, 64), min(self.height - y, 64))
				ret.append(image.crop(bounds))
		return ret

	@property
	def image(self) -> Image:
		"""
		Get a final, compiled image
		"""
		if self._image is None:
			self._image = PIL.Image.new(self.mode, (self.width, self.height), color=None)
			tileNum = 0
			for y in range(0, self.height, 64):
				for x in range(0, self.width, 64):
					subImage = self._tiles[tileNum]
					tileNum += 1
					self._image.paste(subImage, (x, y))
			# self._tiles = None
		return self._image

	@image.setter
	def image(self, image: Image):
		self._image = image
		self._tiles = None
		self.width = image.width
		self.height = image.height
		self.tiles = None

	def __repr__(self, indent: str = ""):
		"""Get a textual representation of this object."""
		ret = []
		ret.append(f"Size: {self.width} x {self.height}")
		return indent + ((f"\n{indent}").join(ret))
