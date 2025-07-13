#!/usr/bin/env python3
"""Stuff related to vectors/paths within a gimp document.
"""
# from .GimpIOBase import GimpIOBase
from __future__ import annotations

from binaryiotools import IO

from .GimpParasites import GimpParasite


class GimpVector:
	"""A gimp brush stroke vector."""

	def __init__(self, parent):
		# GimpIOBase.__init__(self, parent)
		_ = parent
		self.name = ""
		self.uniqueId = 0
		self.visible = True
		self.linked = False
		self.parasites = []
		self.strokes = []

	def decode(self, data: bytes, index: int = 0) -> int:
		"""Decode a byte buffer.

		Args:
			data (bytes): data buffer to decode
			index (int, optional): index within the buffer to start at. Defaults to 0.

		Returns:
			int: offset
		"""
		ioBuf = IO(data, index, boolSize=32)
		self.name = ioBuf.sz754
		self.uniqueId = ioBuf.u32
		self.visible = ioBuf.boolean
		self.linked = ioBuf.boolean
		numParasites = ioBuf.u32
		numStrokes = ioBuf.u32
		for _ in range(numParasites):
			parasite = GimpParasite()
			ioBuf.index = parasite.decode(ioBuf.data, ioBuf.index)
			self.parasites.append(parasite)
		for _ in range(numStrokes):
			gimpstroke = GimpStroke(self)
			ioBuf.index = gimpstroke.decode(ioBuf.data, ioBuf.index)
			self.strokes.append(gimpstroke)
		return ioBuf.index

	def encode(self):
		"""Encode to binary data."""
		ioBuf = IO(boolSize=32)
		ioBuf.sz754 = self.name
		ioBuf.u32 = self.uniqueId
		ioBuf.boolean = self.visible
		ioBuf.boolean = self.linked
		ioBuf.u32 = len(self.parasites)
		ioBuf.u32 = len(self.strokes)
		for parasite in self.parasites:
			ioBuf.addBytes(parasite.encode())
		for gimpstroke in self.strokes:
			ioBuf.addBytes(gimpstroke.encode())
		return ioBuf.data

	def __repr__(self, indent: str = "") -> str:
		"""Get a textual representation of this object."""
		ret = []
		ret.append(f"Name: {self.name}")
		ret.append(f"Unique ID (tattoo): {self.uniqueId}")
		ret.append(f"Visible: {self.visible}")
		ret.append(f"Linked: {self.linked}")
		if self.parasites:
			ret.append("Parasites: ")
			for item in self.parasites:
				ret.append(item.__repr__(indent + "\t"))
		if self.strokes:
			ret.append("Strokes: ")
			for item in self.strokes:
				ret.append(item.__repr__(indent + "\t"))
		return indent + ((f"\n{indent}").join(ret))


class GimpStroke:
	"""A single stroke within a vector."""

	STROKE_TYPES = ["None", "Bezier"]

	def __init__(self, parent):
		# GimpIOBase.__init__(self, parent)
		_ = parent
		self.strokeType = 1  # one of self.STROKE_TYPES
		self.closedShape = True
		self.points = []

	def decode(self, data: bytes, index: int = 0) -> int:
		"""Decode a byte buffer.

		Args:
			data (bytes): data buffer to decode
			index (int, optional): index within the buffer to start at. Defaults to 0.

		Returns:
			int: offset
		"""
		ioBuf = IO(data, index, boolSize=32)
		self.strokeType = ioBuf.u32
		self.closedShape = ioBuf.boolean
		numFloatsPerPoint = ioBuf.u32
		numPoints = ioBuf.u32
		for _ in range(numPoints):
			gimpPoint = GimpPoint(self)
			ioBuf.index = gimpPoint.decode(ioBuf.data, ioBuf.index, numFloatsPerPoint)
			self.points.append(gimpPoint)
		return ioBuf.index

	def encode(self):
		"""Encode to binary data."""
		ioBuf = IO(boolSize=32)
		ioBuf.u32 = self.strokeType
		ioBuf.boolean = self.closedShape
		# ioBuf.u32 = numFloatsPerPoint
		# ioBuf.u32 = numPoints
		for gimpPoint in self.points:
			ioBuf.addBytes(gimpPoint.encode())
		return ioBuf.data

	def __repr__(self, indent: str = ""):
		"""Get a textual representation of this object."""
		ret = []
		ret.append(f"Stroke Type: {self.STROKE_TYPES[self.strokeType]}")
		ret.append(f"Closed: {self.closedShape}")
		ret.append("Points: ")
		for point in self.points:
			ret.append(point.__repr__(indent + "\t"))
		return indent + ((f"\n{indent}").join(ret))


class GimpPoint:
	"""A single point within a stroke."""

	POINT_TYPES = ["Anchor", "Bezier control point"]

	def __init__(self, parent):
		_ = parent
		self.x = 0
		self.y = 0
		self.pressure = 1.0
		self.xTilt = 0.5
		self.yTilt = 0.5
		self.wheel = 0.5
		self.pointType = 0

	def decode(self, data: bytes, index: int = 0, numFloatsPerPoint: int = 0):
		"""Decode a byte buffer.

		Args:
			data (bytes): data buffer to decode
			index (int, optional): index within the buffer to start at. Defaults to 0.
			numFloatsPerPoint (int, optional): required so we know
			how many different brush dynamic measurements are
			inside each point. Defaults to 0.

		Returns:
			int: offset
		"""
		ioBuf = IO(data, index, boolSize=32)
		self.pressure = 1.0
		self.xTilt = 0.5
		self.yTilt = 0.5
		self.wheel = 0.5
		self.pointType = ioBuf.u32
		if numFloatsPerPoint < 1:
			numFloatsPerPoint = int((len(ioBuf.data) - ioBuf.index) / 4)
		self.x = ioBuf.float32
		self.y = ioBuf.float32
		if numFloatsPerPoint > 2:
			self.pressure = ioBuf.float32
			if numFloatsPerPoint > 3:
				self.xTilt = ioBuf.float32
				if numFloatsPerPoint > 4:
					self.yTilt = ioBuf.float32
					if numFloatsPerPoint > 5:
						self.wheel = ioBuf.float32
		return ioBuf.index

	def encode(self):
		"""Encode to binary data."""
		ioBuf = IO(boolSize=32)
		ioBuf.u32 = self.pointType
		ioBuf.float32 = self.x
		ioBuf.float32 = self.y
		if self.pressure is not None:
			ioBuf.float32 = self.pressure
			if self.xTilt is not None:
				ioBuf.float32 = self.xTilt
				if self.yTilt is not None:
					ioBuf.float32 = self.yTilt
					if self.wheel is not None:
						ioBuf.float32 = self.wheel
		return ioBuf.data

	def __repr__(self, indent=""):
		"""Get a textual representation of this object."""
		ret = []
		ret.append(f"Location: ({self.x}" + f",{self.y})")
		ret.append(f"Pressure: {self.pressure}")
		ret.append(f"Location: ({self.xTilt}" + f",{self.yTilt})")
		ret.append(f"Wheel: {self.wheel}")
		return indent + ((f"\n{indent}").join(ret))
