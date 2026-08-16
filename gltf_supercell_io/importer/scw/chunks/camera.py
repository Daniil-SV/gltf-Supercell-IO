from . import ScwChunk, BinaryReader
from dataclasses import dataclass


@dataclass
class ScwCamera(ScwChunk):
	name: str = ""
	x_fov: float = 0.0
	y_fov: float = 0.0
	aspect_ratio: float = 0.0
	z_near: float = 0.0
	z_far: float = 0.0

	def __br_read__(self, br: "BinaryReader", version, *args, **kwargs):
		self.name = br.read_str() or ""
		if version >= 0.5:
			self.x_fov, self.y_fov, self.aspect_ratio, self.z_near, self.z_far = (
				br.read_float(5)
			)
		else:
			raise Exception("Where did you get such file from?")
			br.read_matrix()