#!/usr/bin/env python3
"""Gimp color gradient.
"""
from __future__ import annotations

from io import BytesIO

from . import utils


class GradientSegment:
	"""Single segment within a gradient."""

	BLEND_FUNCTIONS = [
		"linear",
		"curved",
		"sinusoidal",
		"spherical (increasing)",
		"spherical (decreasing)",
		"step",
	]
	COLOR_TYPES = ["RGB", "HSV CCW", "HSV CW"]
	ENDPOINT_COLOR_TYPES = [
		"fixed",
		"foreground",
		"foreground transparent",
		"background",
		"background transparent",
	]

	def __init__(self):
		"""Single segment within a gradient."""
		self.leftPosition = 0
		self.middlePosition = 0.5
		self.rightPosition = 1.0
		self.leftColor = (0, 0, 0, 0)
		self.rightColor = (255, 255, 255, 0)
		self.blendFunc = None  # one of self.BLEND_FUNCTIONS
		self.colorType = None  # one of self.COLOR_TYPES
		self.leftColorType = None  # one of self.ENDPOINT_COLOR_TYPES
		self.rightColorType = None  # one of self.ENDPOINT_COLOR_TYPES

	def getColor(self, percent: float):
		"""Given a decimal percent (1.0 = 100%) retrieve the appropriate color
		for this point in the gradient.
		"""
		_ = self, percent
		raise NotImplementedError()

	def decode(self, dataIn: str):
		"""Decode a byte buffer.

		Args:
			dataIn (str): data buffer to decode

		Raises:
			RuntimeError: [description]
		"""
		data = dataIn.split(" ")
		if len(data) < 11 or len(data) > 15:
			raise RuntimeError(f"Data table is unexpected size. {len(data)}")
		self.leftPosition = float(data[0])
		self.middlePosition = float(data[1])
		self.rightPosition = float(data[2])
		self.leftColor = (float(data[3]), float(data[4]), float(data[5]), float(data[6]))
		self.rightColor = (float(data[7]), float(data[8]), float(data[9]), float(data[10]))
		if len(data) >= 12:
			self.blendFunc = int(data[11])
			if len(data) >= 13:
				self.colorType = int(data[12])
				if len(data) >= 14:
					self.leftColorType = int(data[13])
					if len(data) >= 15:
						self.rightColorType = int(data[14])

	def encode(self):
		"""Encode this to a byte array."""
		ret = []
		ret.append(f"{self.leftPosition:06f}")
		ret.append(f"{self.middlePosition:06f}")
		ret.append(f"{self.rightPosition:06f}")
		for chan in self.leftColor:
			ret.append(f"{chan:06f}")
		for chan in self.rightColor:
			ret.append(f"{chan:06f}")
		if self.blendFunc is not None:
			ret.append(f"{self.blendFunc}")
			if self.colorType is not None:
				ret.append(f"{self.colorType}")
				if self.leftColorType is not None:
					ret.append(f"{self.leftColorType}")
					if self.rightColorType is not None:
						ret.append(f"{self.rightColorType}")
		return " ".join(ret)

	def __repr__(self, indent=""):
		"""Get a textual representation of this object."""
		ret = []
		ret.append(f"Left Position: {self.leftPosition}")
		ret.append(f"Middle Position: {self.middlePosition}")
		ret.append(f"Right Position: {self.rightPosition}")
		ret.append(f"Left Color: {self.leftColor}")
		ret.append(f"Right Color: {self.rightColor}")
		if self.blendFunc:
			ret.append(f"Blend Function: {self.BLEND_FUNCTIONS[self.blendFunc]}")
		if self.colorType:
			ret.append(f"Color Type: {self.COLOR_TYPES[self.colorType]}")
		if self.leftColorType:
			ret.append(f"Left Color Type: {self.ENDPOINT_COLOR_TYPES[self.leftColorType]}")
		if self.rightColorType:
			ret.append(f"Right Color Type: {self.ENDPOINT_COLOR_TYPES[self.rightColorType]}")
		return (f"\n{indent}").join(ret)


class GimpGgrGradient:
	"""Gimp color gradient.

	See:
		https://gitlab.gnome.org/GNOME/gimp/blob/master/devel-docs/ggr.txt
	"""

	def __init__(self, fileName: str | None = None):
		"""GimpGgrGradient.

		Args:
			fileName (str, optional): filename. Defaults to None.
		"""
		self.fileName = None
		self.segments = []
		self.name = ""
		if fileName is not None:
			self.load(fileName)

	def load(self, fileName: BytesIO | str):
		"""Load a gimp file.

		:param fileName: can be a file name or a file-like object
		"""
		self.fileName, data = utils.fileOpen(fileName)
		self.decode(data)

	def decode(self, dataIn: bytes):
		"""Decode a byte buffer.

		Args:
			dataIn (bytes): data buffer to decode

		Raises:
			RuntimeError: File format error.  Magic value mismatch.
		"""
		data = dataIn.decode("utf-8").split("\n")
		data = [l.strip() for l in data]
		if data[0] != "GIMP Gradient":
			raise RuntimeError("File format error.  Magic value mismatch.")
		self.name = data[1].split(":", 1)[-1].strip()
		numSegments = int(data[2])
		for i in range(numSegments):
			gSeg = GradientSegment()
			gSeg.decode(data[i + 3])
			self.segments.append(gSeg)

	def encode(self):
		"""Encode this to a byte array."""
		ret = ["GIMP Gradient"]
		ret.append(f"Name: {self.name}")
		ret.append(str(len(self.segments)))
		for segment in self.segments:
			ret.append(segment.encode())
		return ("\n".join(ret) + "\n").encode("utf-8")

	def save(self, tofileName=None):
		"""Save this gimp image to a file."""
		utils.save(self.encode(), tofileName)

	def getColor(self, percent):
		"""Given a decimal percent (1.0 = 100%) retrieve...

		the appropriate color for this point in the gradient.
		"""
		raise NotImplementedError()

	def __repr__(self, indent=""):
		"""Get a textual representation of this object."""
		ret = []
		if self.fileName is not None:
			ret.append(f"fileName: {self.fileName}")
		ret.append(f"Name: {self.name}")
		for seg in self.segments:
			ret.append(seg.__repr__(indent + "\t"))
		return (f"\n{indent}").join(ret)
