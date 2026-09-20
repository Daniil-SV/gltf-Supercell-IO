from dataclasses import dataclass, field

import numpy as np
from io_scene_gltf2.io.com.constants import ComponentType

from .constants import OdinAttributeFormat as Format
from .constants import OdinAttributeType as Type


@dataclass
class OdinRawVertexAttribute:
    data: np.ndarray
    data_type: str  # DataType
    component_type: ComponentType
    source_format: Format


@dataclass
class OdinVertexAttribute:
    format: Format
    index: int
    name: Type
    offset: int


@dataclass
class OdinVertexDescriptor:
    attributes: list[OdinVertexAttribute] = field(default_factory=list)
    offset: int = 0
    stride: int = 0


@dataclass
class OdinMeshDataInfo:
    vertexDescriptors: list[OdinVertexDescriptor] = field(default_factory=list)


class OdinAttributeReader:
    def __init__(
        self,
        buffer: np.ndarray,
        format: Format,
        type: Type,
        offset: int,
        element_offset: int,
        stride: int,
    ) -> None:
        # Normalize offsets to Python ints so numpy scalar arithmetic cannot overflow
        # when Blender passes indices like np.uint16 during mesh import.
        self.element_offset = int(element_offset)
        self.offset = int(offset)
        self.stride = int(stride)
        self.format = format
        self.type = type
        self.dtype = Format.to_numpy_dtype(self.format)

        # Odin packs skin weights into one UInt32, but decoding expands it to
        # four normalized values.  Those values must stay floating-point:
        # using the storage format's uint32 dtype truncates every fractional
        # influence to zero before Blender's importer can create vertex
        # groups.
        if self.type == Type.a_boneweights and self.format == Format.UInt:
            self.dtype = np.dtype(np.float32)

        self.elements_count = Format.to_element_count(self.format)
        self.normalized = Format.is_normalized(self.format)
        self.matrix: np.ndarray | None = None
        self.data = buffer

    def read(self, offset: int) -> np.ndarray:
        if self.type == Type.a_boneweights and self.format == Format.UInt:
            value = np.frombuffer(self.data, dtype=np.uint32, offset=offset, count=1)[0]
            x = (value >> 21) * 0.0002442
            y = ((value >> 10) & 0x7FF) * 0.0002442
            z = (value & 0x3FF) * 0.0002442
            array = np.array([((1.0 - x) - y) - z, x, y, z], dtype=self.dtype)
        else:
            array = np.frombuffer(
                self.data,
                dtype=self.dtype,
                offset=offset,
                count=self.elements_count,
            )

        if self.normalized and np.issubdtype(self.dtype, np.integer):
            info = np.iinfo(array.dtype.name)
            array = array.astype(np.float32) / info.max

        if self.matrix is not None:
            array = array @ self.matrix[:3] + self.matrix[3]

        # Small fixup for normal attributes
        # Often it present as Vec4 attribute
        # which cause gltf importer to crash
        if self.type == Type.a_normal:
            return array[:3]

        return array

    def __getitem__(self, value: int | np.ndarray):
        if isinstance(value, (int, np.integer)):
            index = int(value)
            offset = self.offset + (self.stride * index) + self.element_offset
            return self.read(offset)

        elif isinstance(value, np.ndarray):
            return np.stack([self.__getitem__(v) for v in value])

        return None
