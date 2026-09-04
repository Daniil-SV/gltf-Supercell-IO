from typing import TYPE_CHECKING

from ..descriptor import ShaderPresetDescriptor

if TYPE_CHECKING:
    from ...shader.importer import ShaderImporter
    from ...shader.exporter import ShaderExporter


# Unlit shader socket map
# Its really simple, so i think we can hold it as simple module constants
DIFFUSE_ENABLED = 0
DIFFUSE_TEX = 1
OPACITY_ENABLED = 2
OPACITY = 3
CLIP_PLANE_ENABLED = 4
CLIP_PLANE = 5


class UnlitShaderPreset(ShaderPresetDescriptor):
    shader_idname = "ScUnlitShader"
    shader_label = "Unlit Shader"

    @staticmethod  # Need this for IDE to work correctly
    def import_shader(shader: "ShaderImporter"):
        UnlitShaderPreset.setup_props(shader)

    @staticmethod
    def export_shader(shader: "ShaderExporter"):
        UnlitShaderPreset.setup_props(shader)

    @staticmethod
    def setup_props(shader: "ShaderImporter | ShaderExporter"):
        shader.setup_opacity_blending(OPACITY_ENABLED, OPACITY)

        UnlitShaderPreset.setup_diffuse(shader)
        UnlitShaderPreset.setup_opacity(shader)
        UnlitShaderPreset.setup_clipping(shader)

    @staticmethod
    def setup_diffuse(shader: "ShaderImporter | ShaderExporter"):
        shader.set_constant_prop("DIFFUSE", DIFFUSE_ENABLED)
        shader.set_texture_prop("diffuseTex2D", DIFFUSE_TEX)
        shader.set_color_prop("diffuse", DIFFUSE_TEX)

    @staticmethod
    def setup_opacity(shader: "ShaderImporter | ShaderExporter"):
        shader.set_float_prop("opacity", OPACITY)
        shader.set_texture_prop("opacityTex2D", OPACITY)

    @staticmethod
    def setup_clipping(shader: "ShaderImporter | ShaderExporter"):
        shader.set_constant_prop("CLIP_PLANE", CLIP_PLANE_ENABLED)
        shader.set_color_prop("clipPlane", CLIP_PLANE)
