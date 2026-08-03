from enum import IntEnum
import numpy as np


class OdinAttributeType(IntEnum):
    a_pos = 0
    a_normal = 1
    a_uv0 = 2
    a_uv1 = 3
    a_color = 4
    a_boneindex = 5
    a_boneweights = 6
    a_tangent = 7
    a_colorMul = 8
    a_colorAdd = 9
    a_model = 10
    a_model2 = 11
    a_model3 = 12
    a_binormal = 13
    a_skinningOffsets = 14
    a_color1 = 15

    @classmethod
    def to_attribute_name(cls, component_type) -> str:
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
            # OdinAttributeType.a_colorAdd: 'COLOR_1',
            # OdinAttributeType.a_colorMul: 'COLOR_2',
        }[component_type]

    @classmethod
    def is_normalized(cls, component_type) -> bool:
        return {
            OdinAttributeType.a_pos: False,
            OdinAttributeType.a_normal: True,
            OdinAttributeType.a_boneindex: False,
            OdinAttributeType.a_boneweights: False,
            OdinAttributeType.a_uv0: True,
            OdinAttributeType.a_uv1: True,
            OdinAttributeType.a_color: False,
            OdinAttributeType.a_color1: False,
            OdinAttributeType.a_tangent: False,
        }[component_type]


class OdinAttributeFormat(IntEnum):
    UByteVector4 = 3
    ColorRGBA = 9
    ByteVector3 = 12
    ShortVector2 = 22
    FloatVector2 = 29
    FloatVector3 = 30
    NormalizedWeightVector = 36

    @classmethod
    def to_numpy_dtype(cls, component_type):
        return {
            OdinAttributeFormat.FloatVector3: np.float32,
            OdinAttributeFormat.ByteVector3: np.byte,
            OdinAttributeFormat.UByteVector4: np.ubyte,
            OdinAttributeFormat.NormalizedWeightVector: np.float32,
            OdinAttributeFormat.FloatVector2: np.float32,
            OdinAttributeFormat.ColorRGBA: np.ubyte,
            OdinAttributeFormat.ShortVector2: np.short,
        }[component_type]

    @classmethod
    def to_element_count(cls, component_type) -> int:
        return {
            OdinAttributeFormat.FloatVector3: 3,
            OdinAttributeFormat.ByteVector3: 3,
            OdinAttributeFormat.UByteVector4: 4,
            OdinAttributeFormat.NormalizedWeightVector: 4,
            OdinAttributeFormat.FloatVector2: 2,
            OdinAttributeFormat.ColorRGBA: 4,
            OdinAttributeFormat.ShortVector2: 2,
        }[component_type]
