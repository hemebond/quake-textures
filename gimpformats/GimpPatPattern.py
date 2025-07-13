#!/usr/bin/env python3
"""Pure python implementation of a gimp pattern file.
"""
from __future__ import annotations

from io import BytesIO

import PIL.Image
from binaryiotools import IO

from . import utils


class GimpPatPattern:
	"""Pure python implementation of a gimp pattern file.

	See:
		https://gitlab.gnome.org/GNOME/gimp/blob/master/devel-docs/pat.txt
	"""

	COLOR_MODES = [None, "L", "LA", "RGB", "RGBA"]

	def __init__(self, fileName: BytesIO | str = None):
		"""Pure python implementation of a gimp pattern file.

		Args:
			fileName (BytesIO, optional): filename or pointer. Defaults to None.
		"""
		self.fileName = None
		self.version = 1
		self.width = 0
		self.height = 0
		self.bpp = 4
		self.mode = self.COLOR_MODES[self.bpp]
		self.name = ""
		self._rawImage = None
		self._image = None
		if fileName is not None:
			self.load(fileName)

	def load(self, fileName: BytesIO | str):
		"""Load a gimp file.

		:param fileName: can be a file name or a file-like object
		"""
		self.fileName, data = utils.fileOpen(fileName)
		self.decode(data)

	def decode(self, data: bytes, index: int = 0):
		"""Decode a byte buffer.

		Args:
			data (bytes): data to decode
			index (int, optional): index to start from. Defaults to 0.

		Raises:
			RuntimeError: "File format error.  Magic value mismatch."

		Returns:
			int: pointer
		"""
		ioBuf = IO(data, index)
		headerSize = ioBuf.u32
		self.version = ioBuf.u32
		self.width = ioBuf.u32
		self.height = ioBuf.u32
		self.bpp = ioBuf.u32
		self.mode = self.COLOR_MODES[self.bpp]
		magic = ioBuf.getBytes(4)
		if magic.decode("ascii") != "GPAT":
			raise RuntimeError("File format error.  Magic value mismatch.")
		nameLen = headerSize - ioBuf.index
		self.name = ioBuf.getBytes(nameLen).decode("UTF-8")
		self._rawImage = ioBuf.getBytes(self.width * self.height * self.bpp)
		self._image = None
		return ioBuf.index

	def encode(self):
		"""Encode to a byte buffer."""
		ioBuf = IO()
		ioBuf.u32 = 24 + len(self.name)
		ioBuf.u32 = self.version
		ioBuf.u32 = self.width
		ioBuf.u32 = self.height
		ioBuf.u32 = len(self.image.mode)
		ioBuf.addBytes("GPAT")
		ioBuf.addBytes(self.name.encode("utf-8"))
		if self._rawImage is None:
			rawImage = self.image.tobytes(encoder_name="raw")
		else:
			rawImage = self._rawImage
		ioBuf.addBytes(rawImage)
		return ioBuf.data

	@property
	def size(self):
		"""The size of the pattern."""
		return (self.width, self.height)

	@property
	def image(self):
		"""Get a final, compiled image."""
		if self._image is None:
			if self._rawImage is None:
				return None
			self._image = PIL.Image.frombytes(
				self.mode, self.size, self._rawImage, decoder_name="raw"
			)
		return self._image

	@image.setter
	def image(self, image):
		self._image = image
		self._rawImage = None

	def save(self, tofileName=None, toExtension=None):
		"""Save this gimp image to a file."""
		asImage = False
		if toExtension is None:
			if tofileName is not None:
				toExtension = tofileName.rsplit(".", 1)
				if len(toExtension) > 1:
					toExtension = toExtension[-1]
				else:
					toExtension = None
		if toExtension is not None and toExtension != "pat":
			asImage = True
		if asImage:
			self.image.save(tofileName)
		else:
			if hasattr(tofileName, "write"):
				file = tofileName
			else:
				file = open(tofileName, "wb")
			file.write(self.encode())
			file.close()

	def __repr__(self):
		"""Get a textual representation of this object."""
		ret = []
		if self.fileName is not None:
			ret.append(f"fileName: {self.fileName}")
		ret.append(f"Name: {self.name}")
		ret.append(f"Version: {self.version}")
		ret.append(f"Size: {self.width} x {self.height}")
		ret.append(f"BPP: {self.bpp}")
		ret.append(f"Mode: {self.mode}")
		return "\n".join(ret)
