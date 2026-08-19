from dataclasses import dataclass

import numpy as np

from .. import BinaryReader, ScwChunk
from .primitive import dtype_from_size


@dataclass
class ScwAttribute(ScwChunk):
    name: str = ""
    triangles_index = 0
    index_set = 0
    data: np.ndarray = None  # type: ignore

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.name = br.read_str() or ""
        self.triangles_index, self.index_set, dimensions = br.read_uint8(3)

        scale = br.read_float()
        count = br.read_uint32()

        self.data = np.frombuffer(
            br.read_bytes(count * dimensions * 2),
            dtype=dtype_from_size(2, unsigned=False),
        ).reshape((count, dimensions)).astype(np.float32)
        
        self.data *= scale / 32512
