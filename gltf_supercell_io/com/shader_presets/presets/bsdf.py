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
        shader.set_surface_color("diffuse", "diffuseTex2D", DIFFUSE_TEX)
        shader.set_surface_color(
            "opacity", "opacityTex2D", OPACITY_TEX, defaultValue=1.0
        )

        ior = 0.0
        roughness = 1.0
        if "metal" in shader.sc_material.name:
            roughness = 0.3
            ior = 0.5

        shader.shader.inputs[IOR_LEVEL].default_value = ior  # type: ignore
        shader.shader.inputs[ROUGHNESS].default_value = roughness  # type: ignore
