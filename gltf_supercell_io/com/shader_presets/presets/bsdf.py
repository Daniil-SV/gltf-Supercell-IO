from typing import TYPE_CHECKING

from ..descriptor import ShaderPresetDescriptor

if TYPE_CHECKING:
    from ...shader.importer import ShaderImporter

DIFFUSE_TEX = 0
OPACITY_TEX = 4
IOR_LEVEL = 13
ROUGHNESS = 2


class BsdfPreset(ShaderPresetDescriptor):
    shader_label = "Principled BSDF"
    shader_idname = "ShaderNodeBsdfPrincipled"

    @staticmethod
    def import_shader(shader: "ShaderImporter"):
        shader.set_texture_prop("diffuseTex2D", DIFFUSE_TEX)
        shader.set_color_prop("diffuse", DIFFUSE_TEX)

        shader.set_float_prop("opacity", OPACITY_TEX)
        shader.set_texture_prop("opacityTex2D", OPACITY_TEX)

        ior = 0.0
        roughness = 1.0
        if "metal" in shader.sc_material.name:
            roughness = 0.3
            ior = 0.5

        shader.shader.inputs[IOR_LEVEL].default_value = ior  # type: ignore
        shader.shader.inputs[ROUGHNESS].default_value = roughness  # type: ignore
