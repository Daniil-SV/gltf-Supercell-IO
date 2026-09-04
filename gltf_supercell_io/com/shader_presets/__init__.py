from enum import StrEnum
from .presets.brawlStarsLegacy import BrawlStarsLegacyShaderPreset
from .presets.unlit import UnlitShaderPreset
from .presets.bsdf import BsdfShaderPreset
from .presets.brawlStars import BrawlStarsShaderPreset
from typing import Type
from .descriptor import ShaderPresetDescriptor


class ShaderPresetType(StrEnum):
    UNLIT = UnlitShaderPreset.shader_idname
    BRAWL_STARS_LEGACY = BrawlStarsLegacyShaderPreset.shader_idname
    BRAWL_STARS = BrawlStarsShaderPreset.shader_idname
    BSDF = BsdfShaderPreset.shader_idname


class ShaderPresets:
    @staticmethod
    def get_preset_by_id(id: str) -> Type[ShaderPresetDescriptor]:
        preset = None
        match (id):
            case ShaderPresetType.UNLIT:
                preset = UnlitShaderPreset

            case ShaderPresetType.BRAWL_STARS_LEGACY:
                preset = BrawlStarsLegacyShaderPreset

            case ShaderPresetType.BRAWL_STARS:
                preset = BrawlStarsShaderPreset

            case ShaderPresetType.BSDF:
                preset = BsdfShaderPreset

            case _:
                raise NotImplementedError()

        return preset
