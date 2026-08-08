from .. import ScwChunk, BinaryReader
import numpy as np
from dataclasses import dataclass

@dataclass
class ScwAttribute(ScwChunk):
    name = ""
    triangles_index = 0
    index_set = 0
    dimensions = 0
    data: np.ndarray = None  # type: ignore

    def __br_read__(self, br: "BinaryReader"):
        self.name = br.read_str()
        self.triangles_index, self.index_set, self.dimensions = br.read_uint8(3)

        scale = br.read_float()
        count = br.read_int32()
        self.data = (
            np.frombuffer(br.read_bytes(count * self.dimensions * 2), dtype=np.short)
            * 0.000030758
        )
        self.data *= scale
