from . import ScwChunk
from typing import Optional, Tuple
from dataclasses import dataclass
from ....com.utilities.binary_reader import BinaryReader, Whence
from mathutils import Matrix
import numpy as np

from .sub.attribute import ScwAttribute
from .sub.joint import ScwJoint
from .sub.primitive import ScwPrimitive

weights_dtype = np.dtype([("joints", np.uint8, (4,)), ("weights", np.uint16, (4,))])


@dataclass
class ScwWeights:
    joints: np.ndarray
    weights: np.ndarray

@dataclass
class ScwGeometry(ScwChunk):
    name: str = "Mesh"
    attributes: Tuple[ScwAttribute, ...] = ()
    bind_matrix: Optional[Matrix] = None
    joints: Tuple[ScwJoint, ...] = ()
    weights: Optional[ScwWeights] = None
    primitives: Tuple[ScwPrimitive, ...] = ()

    def __br_read__(self, br: "BinaryReader", version: int = -1):
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

        weights_count = br.read_int32()
        if weights_count > 0:
            weights_data = br.read_bytes(weights_count * 12)
            weights = np.frombuffer(
                weights_data, dtype=weights_dtype, count=weights_count
            )

            self.weights = ScwWeights(weights["joints"], weights["weights"])

        primitives_count = br.read_uint8()
        self.primitives = br.read_struct(ScwPrimitive, primitives_count)
