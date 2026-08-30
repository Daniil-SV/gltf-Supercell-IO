from dataclasses import dataclass

import numpy as np

from .. import BinaryReader, ScwChunk


def dtype_from_size(size: int, unsigned=True):
    sign = "u" if unsigned else "i"
    match size:
        case 1:
            return np.dtype(f">{sign}{size}")
        case 2:
            return np.dtype(f">{sign}{size}")
        case 4:
            return np.dtype(f">{sign}{size}")
        case _:
            raise ImportError("Incorrect dtype size!")


@dataclass
class ScwPrimitive(ScwChunk):
    material_bind_name = ""
    attribute_indices: tuple[np.ndarray, ...] = ()

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.material_bind_name = br.read_str()

        count = br.read_uint32()
        inputs_count = br.read_uint8()
        size = br.read_uint8()
        
        elements_count = count * inputs_count * 3
        data_size = elements_count * size

        if size == 3:
            data = np.frombuffer(br.read_bytes(data_size), ">u1")
        
            array = np.empty(elements_count, np.uint32)
            array[:] = data[:, 0]
            array <<= 8
            array |= data[:, 1]
            array <<= 8
            array |= data[:, 2]
        else:
            array = np.frombuffer(
                br.read_bytes(data_size), dtype_from_size(size), count=elements_count
            )
        array = array.reshape((count * 3, inputs_count))

        self.attribute_indices = tuple([array[:, i] for i in range(inputs_count)])
