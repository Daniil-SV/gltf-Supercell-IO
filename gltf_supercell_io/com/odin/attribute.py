from .constants import OdinAttributeFormat as Format
import numpy as np

class OdinAttribute:
    def __init__(self, buffer: np.array, format: Format, offset: int, element_offset: int, stride: int) -> None:
        self.element_offset = element_offset
        self.offset = offset
        self.stride = stride
        self.format = format
        self.type = type
        self.dtype = Format.to_numpy_dtype(self.format)
        self.elements_count = Format.to_element_count(self.format)
        self.data = buffer
        
    def read(self, offset: int) -> np.array:
        match(self.format):
            case Format.NormalizedWeightVector:
                value = np.frombuffer(
                    self.data, dtype=np.uint32, offset=offset, count=1
                )[0]
                x = (value >> 21) * 0.0002442
                y = ((value >> 10) & 0x7FF) * 0.0002442
                z = (value & 0x3FF) * 0.0002442
                array = np.array([
                    ((1.0 - x) - y) - z,
                    x,
                    y,
                    z
                ], dtype=self.dtype)
            case _:
                array = np.frombuffer(
                    self.data, dtype=self.dtype, offset=offset, count=self.elements_count
                )

        return array

    def __getitem__(self, value: any):
        if (isinstance(value, int) or isinstance(value, np.integer)):
            offset = self.offset + (self.stride * value) + self.element_offset
            return self.read(offset)
        
        elif (isinstance(value, np.ndarray)):
            return [
                self.__getitem__(v) for v in value
            ]
            
        return None