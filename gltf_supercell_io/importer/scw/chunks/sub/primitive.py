from .. import ScwChunk, BinaryReader
import numpy as np
from dataclasses import dataclass


def dtype_from_size(size: int):
    match size:
        case 1:
            return np.dtype(">u1")
        case 2:
            return np.dtype(">u2")
        case 4:
            return np.dtype(">u4")
        case 8:
            return np.dtype(">u8")
        case _:
            raise ImportError("Incorrect SCW mesh triangle index size!")


@dataclass
class ScwPrimitive(ScwChunk):
    material_bind_name = ""
    attribute_triangles: tuple[np.ndarray, ...] = ()

    def __br_read__(self, br: "BinaryReader"):
        self.material_bind_name = br.read_str()

        count = br.read_int32()
        inputs_count = br.read_uint8()
        size = br.read_uint8()

        size_dtype = dtype_from_size(size)
        data_size = count * inputs_count * 3 * size
        dtypes = [(f"f{i}", size_dtype, (3,)) for i in range(inputs_count)]
        arr = np.frombuffer(br.read_bytes(data_size), np.dtype(dtypes), count=count)
        self.attribute_triangles = tuple([arr[f"f{i}"] for i in range(inputs_count)])
