from __future__ import annotations

from io import BytesIO


def fileOpen(fileName: BytesIO | str) -> tuple[str, bytes]:
	if isinstance(fileName, str):
		file = open(fileName, "rb")
	else:
		fileName = fileName.name
		file = fileName
	data = file.read()
	file.close()
	return fileName, data


def save(data: bytes, tofileName: BytesIO | str):
	"""Save this gimp image to a file."""
	if isinstance(tofileName, str):
		file = open(tofileName, "wb")
	else:
		file = tofileName
	file.write(data)
	file.close()
