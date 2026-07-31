from enum import StrEnum
from .presets.brawlStarsLegacy import BrawlStarsLegacy
from .presets.unlit import UnlitPreset
from .presets.bsdf import BsdfPreset
from typing import Type
from .descriptor import ShaderPresetDescriptor


class ShaderPresetType(StrEnum):
    UNLIT = UnlitPreset.shader_idname
    BRAWL_STARS_LEGACY = BrawlStarsLegacy.shader_idname
    BSDF = BsdfPreset.shader_idname


class ShaderPresets:
    @staticmethod
    def get_preset_by_id(id: str) -> Type[ShaderPresetDescriptor]:
        preset = None
        match (id):
            case ShaderPresetType.UNLIT:
                preset = UnlitPreset

            case ShaderPresetType.BRAWL_STARS_LEGACY:
                preset = BrawlStarsLegacy

            case ShaderPresetType.BSDF:
                preset = BsdfPreset

            case _:
                raise NotImplementedError()

        return preset
