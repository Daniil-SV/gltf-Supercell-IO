from .. import ScwChunk, BinaryReader
import numpy as np
from dataclasses import dataclass


def dtype_from_size(size: int, unsigned=True):
    sign = "u" if unsigned else "i"
    match size:
        case 1:
            return np.dtype(f">{sign}{size}")
        case 2:
            return np.dtype(f">{sign}{size}")
        case 3:
            raise Exception(
                "Got datatype with size `3`, which is unsupported for now"
            )  # np doesnt really support uint24
        case 4:
            return np.dtype(f">{sign}{size}")
        case _:
            raise ImportError("Incorrect SCW data size!")


@dataclass
class ScwPrimitive(ScwChunk):
    material_bind_name = ""
    attribute_indices: tuple[np.ndarray, ...] = ()

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.material_bind_name = br.read_str()

        count = br.read_uint32()
        inputs_count = br.read_uint8()
        size = br.read_uint8()

        size_dtype = dtype_from_size(size)
        elements_count = count * inputs_count * 3
        data_size = elements_count * size
        array = np.frombuffer(
            br.read_bytes(data_size), size_dtype, count=elements_count
        ).reshape((count * 3, inputs_count))

        self.attribute_indices = tuple([array[:, i] for i in range(inputs_count)])
