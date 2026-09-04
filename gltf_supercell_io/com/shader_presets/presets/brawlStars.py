from bpy.types import NodeSocket
from ..descriptor import ShaderPresetDescriptor
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...shader.importer import ShaderImporter
    from ...shader.exporter import ShaderExporter

CONSTANT_MAP = {
    0: "AMBIENT",
    2: "DIFFUSE",
    4: "SPECULAR",
    7: "COLORIZE",
    9: "LIGHTMAP",
    14: "EMISSION",
    16: "STENCIL",
    20: "CLIP_PLANE",
    22: "COLORTRANSFORM_ADD",  # Not sure about that, but it was smth like that
    24: "COLORTRANSFORM_MUL",
}

BOOLEAN_MAP = {29: "enableGlow", 31: "enableGlowDirectional", 33: "enableGlowSpherical"}

FLOAT_MAP = {}

ARRAY_MAP = {1: "ambient", 21: "clipPlane"}

TEXTURE_MAP = {
    8: "colorize",
    3: "diffuse",
    15: "emission",
    6: "specular",
}

LIGHTMAP_MAP = {
    10: "lightmapDiffuse",
    11: "lightmapSpecular",
}

OPACITY_ENABLE = 12
OPACITY = 13
STENCIL_ENABLE = 17
STENCIL_TEXTURE = 18


class BrawlStarsShaderPreset(ShaderPresetDescriptor):
    shader_idname = "ScBrawlStarsShader"
    shader_label = "Brawl Stars Shader"

    @staticmethod
    def setup_props(
        shader: "ShaderImporter | ShaderExporter",
        light_vector: Optional[NodeSocket] = None,
    ):
        shader.setup_opacity_blending(OPACITY_ENABLE, OPACITY)

        for idx, key in CONSTANT_MAP.items():
            shader.set_constant_prop(key, idx)

        for idx, key in ARRAY_MAP.items():
            shader.set_color_prop(key, idx)

        for idx, key in TEXTURE_MAP.items():
            shader.set_surface_color(key, f"{key}Tex", idx)

        for idx, key in LIGHTMAP_MAP.items():
            shader.set_surface_color(
                key, key, idx, vector=light_vector, has_color=False
            )

        shader.set_surface_color("opacity", "opacityTex", OPACITY, defaultValue=1.0)
        shader.set_bool_prop("enableStencilTex", STENCIL_ENABLE)
        shader.set_texture_prop("stencilTex2D", STENCIL_TEXTURE)

    @staticmethod
    def import_shader(shader: "ShaderImporter"):
        lighting_node = shader.instantiate_utility("ScLightmapUV", "Lightmaps")
        lighting_vector = lighting_node.outputs[0]

        BrawlStarsShaderPreset.setup_props(shader, lighting_vector)

    @staticmethod
    def export_shader(shader: "ShaderExporter"):
        BrawlStarsShaderPreset.setup_props(shader)
