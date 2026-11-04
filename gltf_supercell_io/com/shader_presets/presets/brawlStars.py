from typing import TYPE_CHECKING

from bpy.types import NodeSocket

from ...materials.variables import (
    ShaderBooleanProperty,
    ShaderFloatProperty,
)
from ...shader.importer import ShaderImporter
from ...shader.nodes import ShaderNodeScUtility
from ..descriptor import ShaderPresetDescriptor

if TYPE_CHECKING:
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
    3: "diffuse",
    15: "emission",
    6: "specular",
}

LIGHTMAP_MAP = {
    10: "lightmapDiffuse",
    11: "lightmapSpecular",
}

COLORIZE = 8
OPACITY_ENABLE = 12
OPACITY = 13
STENCIL_ENABLE = 17
STENCIL_TEXTURE = 18


class BrawlStarsShaderPreset(ShaderPresetDescriptor):
    shader_idname = "ScBrawlStarsShader"
    shader_label = "Brawl Stars Shader"

    @staticmethod
    def import_sscolorize(shader: "ShaderImporter"):
        sscolorize = shader.sc_material.get_property(
            "enableSSColorize", ShaderBooleanProperty
        )

        ssuv_vector = None
        if sscolorize is not None and sscolorize.status:
            ssuv = shader.instantiate_utility(
                "ScAnimatedScreenSpaceUV", "Screen Space UV"
            )
            ssuv_vector = ssuv.outputs[0]

            scale_soc = ssuv.inputs[0]
            speed_soc = ssuv.inputs[1]
            if ShaderImporter.is_float_socket(scale_soc, "SS Scale"):
                scale = shader.sc_material.get_property(
                    "screenSpaceTextureScale", ShaderFloatProperty
                )

                scale_soc.default_value = 1.0 if scale is None else scale.value

            if ShaderImporter.is_float_socket(speed_soc, "SS Speed"):
                speed = shader.sc_material.get_property(
                    "screenSpaceTextureSpeed", ShaderFloatProperty
                )

                speed_soc.default_value = 0.0 if speed is None else speed.value

        shader.set_surface_color("colorize", "colorizeTex", COLORIZE, ssuv_vector)

    @staticmethod
    def export_sscolorize(shader: "ShaderExporter"):
        shader.set_surface_color("colorize", "colorizeTex", COLORIZE)
        node = shader.get_texture_vector("colorize", COLORIZE)

        enabled = False
        scale = 1.0
        speed = 0.0
        if (
            isinstance(node, ShaderNodeScUtility)
            and node.tree_id == "ScAnimatedScreenSpaceUV"
        ):
            enabled = True
            scale_soc = node.inputs[0]
            if ShaderImporter.is_float_socket(scale_soc, "SS Scale"):
                scale = scale_soc.default_value

            speed_soc = node.inputs[1]
            if ShaderImporter.is_float_socket(speed_soc, "SS Speed"):
                speed = speed_soc.default_value

        shader.sc_material.add_property(
            "enableSSColorize", enabled, ShaderBooleanProperty
        )

        shader.sc_material.add_property(
            "screenSpaceTextureScale", scale, ShaderFloatProperty
        )

        shader.sc_material.add_property(
            "screenSpaceTextureSpeed", speed, ShaderFloatProperty
        )

    @staticmethod
    def setup_props(
        shader: "ShaderImporter | ShaderExporter",
        light_vector: NodeSocket | None = None,
    ):
        shader.setup_opacity_blending(OPACITY_ENABLE, OPACITY)

        for idx, key in CONSTANT_MAP.items():
            shader.set_constant_prop(key, idx)

        for idx, key in ARRAY_MAP.items():
            shader.set_color_prop(key, idx)

        for idx, key in TEXTURE_MAP.items():
            shader.set_surface_color(key, f"{key}Tex", idx)

        # Colorize handling
        if isinstance(shader, ShaderImporter):
            BrawlStarsShaderPreset.import_sscolorize(shader)
        else:
            BrawlStarsShaderPreset.export_sscolorize(shader)

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
