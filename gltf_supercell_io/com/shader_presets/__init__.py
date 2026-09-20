from enum import StrEnum

from .descriptor import ShaderPresetDescriptor
from .presets.brawlStars import BrawlStarsShaderPreset
from .presets.brawlStarsLegacy import BrawlStarsLegacyShaderPreset
from .presets.bsdf import BsdfShaderPreset
from .presets.unlit import UnlitShaderPreset


class ShaderPresetType(StrEnum):
    UNLIT = UnlitShaderPreset.shader_idname
    BRAWL_STARS_LEGACY = BrawlStarsLegacyShaderPreset.shader_idname
    BRAWL_STARS = BrawlStarsShaderPreset.shader_idname
    BSDF = BsdfShaderPreset.shader_idname


class ShaderPresets:
    @staticmethod
    def get_preset_by_id(id: str) -> type[ShaderPresetDescriptor]:
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
