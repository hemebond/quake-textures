"""Gets packed pixels from a gimp image.

NOTE: This was originally designed to be a hierarchy, like
	an image pyramid, through in practice they only use the
	top level of the pyramid (64x64) and ignore the rest.
"""
from __future__ import annotations

from PIL import Image

from .GimpImageLevel import GimpImageLevel
from .GimpIOBase import IO, GimpIOBase


class GimpImageHierarchy(GimpIOBase):
	"""
	Gets packed pixels from a gimp image

	NOTE: This was originally designed to be a hierarchy, like
		an image pyramid, through in practice they only use the
		top level of the pyramid (64x64) and ignore the rest.
	"""

	def __init__(self, parent, image: Image.Image | None = None):
		GimpIOBase.__init__(self, parent)
		self.width: int = 0
		self.height: int = 0
		self.bpp: int = 0  # Number of bytes per pixel given
		self._levelPtrs = []
		self._levels = None
		self._data = None
		if image is not None:  # NOTE: can override earlier parameters
			self.image = image

	def decode(self, data: bytes, index: int = 0):
		"""
		decode a byte buffer

		:param data: data buffer to decode
		:param index: index within the buffer to start at
		"""
		if not data:
			raise RuntimeError("No data!")
		ioBuf = IO(data, index)
		# print 'Decoding channel at',index
		self.width = ioBuf.u32
		self.height = ioBuf.u32
		self.bpp = ioBuf.u32
		if self.bpp < 1 or self.bpp > 4:
			msg = (
				"""'Unexpected bytes-per-pixel for image data ("""
				+ str(self.bpp)
				+ """).
				Probably means file corruption."""
			)
			raise RuntimeError(msg)
		while True:
			ptr = self._pointerDecode(ioBuf)
			if ptr == 0:
				break
			self._levelPtrs.append(ptr)
		if self._levelPtrs:  # remove "dummy" level pointers
			self._levelPtrs = [self._levelPtrs[0]]
		self._data = data
		return ioBuf.index

	def encode(self):
		"""Encode this object to a byte buffer."""
		dataioBuf = IO()
		ioBuf = IO()
		ioBuf.u32 = self.width
		ioBuf.u32 = self.height
		ioBuf.u32 = self.bpp
		dataIndex = ioBuf.index + self.pointerSize * (len(self.levels) + 1)
		for level in self.levels:
			ioBuf.addBytes(
				self._pointerEncode(dataIndex + dataioBuf.index)
			)  # TODO: This may be incorrect
			dataioBuf.addBytes(level.encode())
		ioBuf.addBytes(self._pointerEncode(0))
		ioBuf.addBytes(dataioBuf.data)
		return ioBuf.data

	@property
	def levels(self):
		"""Get the levels within this hierarchy.

		Presently hierarchy is not really used by gimp,
		so this returns an array of one item
		"""
		if self._levels is None:
			for ptr in self._levelPtrs:
				level = GimpImageLevel(self)
				level.decode(self._data, ptr)
				self._levels = [level]
		return self._levels

	@property
	def image(self) -> Image.Image | None:
		"""Get a final, compiled image."""
		if not self.levels:
			return None
		return self.levels[0].image

	@image.setter
	def image(self, image: Image.Image):
		"""Set the image."""
		self.width = image.width
		self.height = image.height
		if image.mode not in ["L", "LA", "RGB", "RGBA"]:
			raise NotImplementedError("Unsupported PIL image type")
		self.bpp = len(image.mode)
		self._levelPtrs = None
		# self._levels = [GimpImageLevel(self, image)]

	def __repr__(self, indent: str = ""):
		"""Get a textual representation of this object."""
		ret = []
		ret.append(f"Size: {self.width} x {self.height}")
		ret.append(f"Bytes Per Pixel: {self.bpp}")
		return indent + ((f"\n{indent}").join(ret))
