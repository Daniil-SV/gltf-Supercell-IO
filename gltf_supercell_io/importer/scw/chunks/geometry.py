from dataclasses import dataclass
from typing import Optional

import numpy as np
from mathutils import Matrix

from ....com.utilities.binary_reader import BinaryReader, Whence
from . import ScwChunk
from .sub.attribute import ScwAttribute
from .sub.joint import ScwJoint
from .sub.primitive import ScwPrimitive, dtype_from_size

weights_dtype = np.dtype(
	[("joints", dtype_from_size(1), (4,)), ("weights", dtype_from_size(2), (4,))]
)
old_weights_dtype = np.dtype(
	[("joints", dtype_from_size(1), (4,)), ("weights", dtype_from_size(1), (4,))]
)


@dataclass
class ScwWeights:
	joints: np.ndarray
	weights: np.ndarray


@dataclass
class ScwGeometry(ScwChunk):
	name: str = "Mesh"
	attributes: tuple[ScwAttribute, ...] = ()
	bind_matrix: Optional[Matrix] = None
	joints: tuple[ScwJoint, ...] = ()
	weights: Optional[ScwWeights] = None
	primitives: tuple[ScwPrimitive, ...] = ()

	def __br_read__(self, br: "BinaryReader", version: int = -1, *args, **kwargs):
		self.name = br.read_str() or "Mesh"
		br.read_str()  # Group name

		if version <= 1:
			br.seek(16 * 4, Whence.CUR)

		attributes_count = br.read_uint8()
		self.attributes = br.read_struct(ScwAttribute, attributes_count)

		has_bind_matrix = br.read_bool()
		if has_bind_matrix:
			self.bind_matrix = br.read_matrix()

		joints_count = br.read_uint8()
		self.joints = br.read_struct(ScwJoint, joints_count)

		weight_count = br.read_uint32()
		if weight_count > 0:
			# a /= b, xyz(a) is faster than xyz(a / b)
			if version >= 0.5:
				weights_data = br.read_bytes(weight_count * 12)
				weights = np.frombuffer(
					weights_data, weights_dtype, weight_count
				)
				weights["weights"] /= 0xFFFF
			else:
				weights_data = br.read_bytes(weight_count * 8)
				weights = np.frombuffer(
					weights_data, old_weights_dtype, weight_count
				)
				weights["weights"] /= 0xFF
	
			self.weights = ScwWeights(weights["joints"], weights["weights"])

		primitives_count = br.read_uint8()
		self.primitives = br.read_struct(ScwPrimitive, primitives_count)
