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
    12: "OPACITY",
    14: "EMISSION",
    16: "STENCIL",
    20: "CLIP_PLANE",
    22: "COLORTRANSFORM_ADD",  # Not sure about that, but it was smth like that
    24: "COLORTRANSFORM_MUL",
}

ARRAY_MAP = {1: "ambient", 21: "clipPlane"}

TEXTURE_MAP = {
    8: "colorize",
    3: "diffuse",
    15: "emission",
    6: "specular",
}

LIGHTMAP_MAP = {
    10: "lightmap",
    11: "lightmapSpecular",
}

OPACITY = 13
STENCIL_ENABLE = 17
STENCIL_TEXTURE = 18


class BrawlStarsLegacy(ShaderPresetDescriptor):
    shader_idname = "ScLegacyBrawlStarsShader"
    shader_label = "Brawl Stars Legacy Shader"

    @staticmethod
    def setup_props(
        shader: "ShaderImporter | ShaderExporter",
        light_vector: Optional[NodeSocket] = None,
    ):
        for idx, key in CONSTANT_MAP.items():
            shader.set_constant_prop(key, idx)

        for idx, key in ARRAY_MAP.items():
            shader.set_color_prop(key, idx)

        for idx, key in TEXTURE_MAP.items():
            shader.set_surface_color(key, f"{key}Tex2D", idx)

        for idx, key in LIGHTMAP_MAP.items():
            shader.set_surface_color(
                key, f"{key}Tex2D", idx, vector=light_vector, has_color=False
            )

        shader.set_surface_color("opacity", "opacityTex2D", OPACITY, defaultValue=1.0)
        shader.set_bool_prop("enableStencilTex", STENCIL_ENABLE)
        shader.set_texture_prop("stencilTex2D", STENCIL_TEXTURE)

    @staticmethod
    def import_shader(shader: "ShaderImporter"):
        lighting_node = shader.instantiate_utility("ScLightmapUV", "Lightmaps")
        lighting_vector = lighting_node.outputs[0]

        BrawlStarsLegacy.setup_props(shader, lighting_vector)

    @staticmethod
    def export_shader(shader: "ShaderExporter"):
        shader.set_blend_from_opacity_socket(OPACITY)
        BrawlStarsLegacy.setup_props(shader)
