from enum import IntEnum, StrEnum, auto

import numpy as np
from io_scene_gltf2.io.com.constants import ComponentType


class OdinAttributeType(StrEnum):
    a_pos = auto()
    a_normal = auto()
    a_uv0 = auto()
    a_uv1 = auto()
    a_color = auto()
    a_boneindex = auto()
    a_boneweights = auto()
    a_tangent = auto()
    a_colorMul = auto()
    a_colorAdd = auto()
    a_model = auto()
    a_model2 = auto()
    a_model3 = auto()
    a_binormal = auto()
    a_skinningOffsets = auto()
    a_color1 = auto()

    @classmethod
    def to_index(cls, component_type: "OdinAttributeType") -> int:
        return {
            OdinAttributeType.a_pos: 0,
            OdinAttributeType.a_normal: 1,
            OdinAttributeType.a_uv0: 2,
            OdinAttributeType.a_uv1: 3,
            OdinAttributeType.a_color: 4,
            OdinAttributeType.a_boneindex: 5,
            OdinAttributeType.a_boneweights: 6,
            OdinAttributeType.a_tangent: 7,
            OdinAttributeType.a_colorMul: 8,
            OdinAttributeType.a_colorAdd: 9,
            OdinAttributeType.a_model: 10,
            OdinAttributeType.a_model2: 11,
            OdinAttributeType.a_model3: 12,
            OdinAttributeType.a_binormal: 13,
            OdinAttributeType.a_skinningOffsets: 14,
            OdinAttributeType.a_color1: 15,
        }[component_type]

    @classmethod
    def to_attribute_name(cls, component_type: "OdinAttributeType") -> str:
        return {
            OdinAttributeType.a_pos: "POSITION",
            OdinAttributeType.a_normal: "NORMAL",
            OdinAttributeType.a_boneindex: "JOINTS_0",
            OdinAttributeType.a_boneweights: "WEIGHTS_0",
            OdinAttributeType.a_uv0: "TEXCOORD_0",
            OdinAttributeType.a_uv1: "TEXCOORD_1",
            OdinAttributeType.a_color: "COLOR_0",
            OdinAttributeType.a_color1: "COLOR_1",
            OdinAttributeType.a_tangent: "TANGENT",
        }[component_type]

    @classmethod
    def from_attribute_name(cls, component_type: str) -> "OdinAttributeType | None":
        mapping = {
            "POSITION": OdinAttributeType.a_pos,
            "NORMAL": OdinAttributeType.a_normal,
            "JOINTS_0": OdinAttributeType.a_boneindex,
            "WEIGHTS_0": OdinAttributeType.a_boneweights,
            "TEXCOORD_0": OdinAttributeType.a_uv0,
            "TEXCOORD_1": OdinAttributeType.a_uv1,
            "COLOR_0": OdinAttributeType.a_color,
            "COLOR_1": OdinAttributeType.a_color1,
            "TANGENT": OdinAttributeType.a_tangent,
        }

        if component_type in mapping:
            return mapping[component_type]


class OdinAttributeFormat(IntEnum):
    UByte2 = 1
    UByte3 = 2
    UByte4 = 3

    Byte2 = 4
    Byte3 = 5
    Byte4 = 6

    UByte2Norm = 7
    UByte3Norm = 8
    UByte4Norm = 9

    Byte2Norm = 10
    Byte3Norm = 11
    Byte4Norm = 12

    UShort2 = 13
    UShort3 = 14
    UShort4 = 15

    Short2 = 16
    Short3 = 17
    Short4 = 18

    UShort2Norm = 19
    UShort3Norm = 20
    UShort4Norm = 21

    Short2Norm = 22
    Short3Norm = 23
    Short4Norm = 24

    Half2 = 25
    Half3 = 26
    Half4 = 27

    Float = 28
    Float2 = 29
    Float3 = 30
    Float4 = 31

    Int = 32
    Int2 = 33
    Int3 = 34
    Int4 = 35

    UInt = 36
    UInt2 = 37
    UInt3 = 38
    UInt4 = 39

    Int1010102Norm = 40
    UInt1010102Norm = 41

    Float2x2 = 100
    Float3x3 = 101
    Float4x4 = 102

    @classmethod
    def to_numpy_dtype(cls, component_type) -> np.dtype:
        component_type = cls(component_type)

        dtype = None
        if component_type in (
            cls.UByte2,
            cls.UByte3,
            cls.UByte4,
            cls.UByte2Norm,
            cls.UByte3Norm,
            cls.UByte4Norm,
        ):
            dtype = np.uint8

        if component_type in (
            cls.Byte2,
            cls.Byte3,
            cls.Byte4,
            cls.Byte2Norm,
            cls.Byte3Norm,
            cls.Byte4Norm,
        ):
            dtype = np.int8

        if component_type in (
            cls.UShort2,
            cls.UShort3,
            cls.UShort4,
            cls.UShort2Norm,
            cls.UShort3Norm,
            cls.UShort4Norm,
        ):
            dtype = np.uint16

        if component_type in (
            cls.Short2,
            cls.Short3,
            cls.Short4,
            cls.Short2Norm,
            cls.Short3Norm,
            cls.Short4Norm,
        ):
            dtype = np.int16

        if component_type in (cls.Half2, cls.Half3, cls.Half4):
            dtype = np.float16

        if component_type in (cls.Float, cls.Float2, cls.Float3, cls.Float4):
            dtype = np.float32

        if component_type in (
            cls.UInt,
            cls.UInt2,
            cls.UInt3,
            cls.UInt4,
            cls.UInt1010102Norm,
        ):
            dtype = np.uint32

        if component_type == cls.Float2x2:
            return np.dtype([("value", np.float32, (2, 2))])

        if component_type == cls.Float3x3:
            return np.dtype([("value", np.float32, (3, 3))])

        if component_type == cls.Float4x4:
            return np.dtype([("value", np.float32, (4, 4))])

        if dtype is not None:
            return np.dtype(dtype)

        raise ValueError(f"Unsupported Odin attribute format: {component_type}")

    @classmethod
    def to_element_count(cls, component_type) -> int:
        component_type = cls(component_type)

        if component_type in (
            cls.UByte2,
            cls.Byte2,
            cls.UByte2Norm,
            cls.Byte2Norm,
            cls.UShort2,
            cls.Short2,
            cls.UShort2Norm,
            cls.Short2Norm,
            cls.Half2,
            cls.Float2,
            cls.Int2,
            cls.UInt2,
        ):
            return 2

        if component_type in (
            cls.UByte3,
            cls.Byte3,
            cls.UByte3Norm,
            cls.Byte3Norm,
            cls.UShort3,
            cls.Short3,
            cls.UShort3Norm,
            cls.Short3Norm,
            cls.Half3,
            cls.Float3,
            cls.Int3,
            cls.UInt3,
        ):
            return 3

        if component_type in (
            cls.UByte4,
            cls.Byte4,
            cls.UByte4Norm,
            cls.Byte4Norm,
            cls.UShort4,
            cls.Short4,
            cls.UShort4Norm,
            cls.Short4Norm,
            cls.Half4,
            cls.Float4,
            cls.Int4,
            cls.UInt4,
        ):
            return 4

        if component_type in (
            cls.Float,
            cls.Int,
            cls.UInt,
            cls.Int1010102Norm,
            cls.UInt1010102Norm,
        ):
            return 1

        if component_type in (cls.Float2x2, cls.Float3x3, cls.Float4x4):
            return 1

        raise ValueError(f"Unsupported Odin attribute format: {component_type}")

    @classmethod
    def is_normalized(cls, component_type) -> bool:
        component_type = cls(component_type)
        return component_type in (
            cls.UByte2Norm,
            cls.UByte3Norm,
            cls.UByte4Norm,
            cls.Byte2Norm,
            cls.Byte3Norm,
            cls.Byte4Norm,
            cls.UShort2Norm,
            cls.UShort3Norm,
            cls.UShort4Norm,
            cls.Short2Norm,
            cls.Short3Norm,
            cls.Short4Norm,
            cls.Int1010102Norm,
            cls.UInt1010102Norm,
        )

    @classmethod
    def from_components(cls, type: str, component_type: ComponentType):
        if type == "SCALAR":
            match (component_type):
                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt
                case ComponentType.Float:
                    return OdinAttributeFormat.Float

        if type == "VEC2":
            match (component_type):
                case ComponentType.Byte:
                    return OdinAttributeFormat.Byte2
                case ComponentType.UnsignedByte:
                    return OdinAttributeFormat.UByte2

                case ComponentType.Short:
                    return OdinAttributeFormat.Short2
                case ComponentType.UnsignedShort:
                    return OdinAttributeFormat.UShort2

                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt2
                case ComponentType.Float:
                    return OdinAttributeFormat.Float2

        if type == "VEC3":
            match (component_type):
                case ComponentType.Byte:
                    return OdinAttributeFormat.Byte3
                case ComponentType.UnsignedByte:
                    return OdinAttributeFormat.UByte3

                case ComponentType.Short:
                    return OdinAttributeFormat.Short3
                case ComponentType.UnsignedShort:
                    return OdinAttributeFormat.UShort3

                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt3
                case ComponentType.Float:
                    return OdinAttributeFormat.Float3

        if type == "VEC4":
            match (component_type):
                case ComponentType.Byte:
                    return OdinAttributeFormat.Byte4
                case ComponentType.UnsignedByte:
                    return OdinAttributeFormat.UByte4

                case ComponentType.Short:
                    return OdinAttributeFormat.Short4
                case ComponentType.UnsignedShort:
                    return OdinAttributeFormat.UShort4

                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt4
                case ComponentType.Float:
                    return OdinAttributeFormat.Float4

        if type == "MAT2" and component_type == ComponentType.Float:
            return OdinAttributeFormat.Float3x3

        if type == "MAT3" and component_type == ComponentType.Float:
            return OdinAttributeFormat.Float2x2

        if type == "MAT4" and component_type == ComponentType.Float:
            return OdinAttributeFormat.Float4x4

        raise Exception("Unsupported odin mesh format")
