from pathlib import PurePath
import bpy
from bpy.types import Material, Image, NodeSocketFloatFactor
from ..materials import ScShaderMaterial, ScBlendMode
from .nodes import ShaderNodeScShader
from ..shader_presets import ShaderPresets
from ..utilities import typing
from ..materials.variables import (
    ShaderFloatVectorProperty,
    ShaderFloatProperty,
    ShaderBooleanProperty,
    ShaderTextureProperty,
)
from io_scene_gltf2.blender.exp.material.search_node_tree import (
    has_image_node_from_socket,
    NodeSocket,
)
from io_scene_gltf2.blender.exp.material.image import __make_image as make_image
from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.blender.exp.cache import cached
from io_scene_gltf2.io.com.constants import TextureFilter, TextureWrap
from ..utilities.shader import ShaderUtils
from typing import Any


class ShaderExporter:

    def __init__(
        self,
        shader: ShaderNodeScShader,
        material: Material,
        modifiers: list[str],
        export_settings: dict,
    ):
        self.shader = shader
        self.material = material
        self.sc_material = ScShaderMaterial()
        self.preset = ShaderPresets.get_preset_by_id(shader.preset_id)
        self.modifiers = modifiers
        self.export_settings = export_settings

    def set_blend_from_opacity_socket(self, index: int):
        """Set the blend mode based on the opacity socket"""
        socket = self.shader.inputs[index]
        if not isinstance(socket, NodeSocketFloatFactor):
            print("Warning: Failed to get opacity float socket in SC IO shader")
            return

        has_alpha = False
        if (
            has_image_node_from_socket(NodeSocket(socket, []), {})
            or socket.default_value != 1.0
        ):
            has_alpha = True

        render_method = self.material.surface_render_method
        if has_alpha and render_method == "DITHERED":
            self.sc_material.blend_mode = ScBlendMode.ADDITIVE
        elif has_alpha and render_method == "BLENDED":
            self.sc_material.blend_mode = ScBlendMode.PREMULTIPLIED
        elif render_method == "BLENDED":
            self.sc_material.blend_mode = ScBlendMode.MULTIPLY
        else:
            self.sc_material.blend_mode = ScBlendMode.OPAQUE

    def set_constant_prop(self, name: str, index: int):
        """Set the constant based on the boolean socket"""
        socket = self.shader.inputs[index]
        if not ShaderUtils.is_bool_socket(socket, name):
            return

        enabled = socket.default_value
        if enabled:
            self.sc_material.add_constant(name)

    @cached
    @staticmethod
    def create_legacy_sampler(extension, interpolation, export_settings: dict):
        wrap_s = None
        wrap_t = None
        mag_filter = None
        min_filter = None

        # First gather from the Texture node
        if extension == "EXTEND":
            wrap_s = TextureWrap.ClampToEdge
        elif extension == "CLIP":
            # Not possible in glTF, but ClampToEdge is closest
            wrap_s = TextureWrap.ClampToEdge
        elif extension == "MIRROR":
            wrap_s = TextureWrap.MirroredRepeat
        else:
            wrap_s = TextureWrap.Repeat
        wrap_t = wrap_s

        if (wrap_s, wrap_t) == (TextureWrap.Repeat, TextureWrap.Repeat):
            wrap_s, wrap_t = None, None

        if interpolation == "Closest":
            mag_filter = TextureFilter.Nearest
            min_filter = TextureFilter.NearestMipmapNearest
        else:
            mag_filter = TextureFilter.Linear
            min_filter = TextureFilter.LinearMipmapLinear

        return gltf2_io.Sampler(
            extensions=None,
            extras=None,
            mag_filter=mag_filter,
            min_filter=min_filter,
            name=None,
            wrap_s=wrap_s,
            wrap_t=wrap_t,
        )

    @cached
    @staticmethod
    def create_legacy_texture_info(
        sampler: gltf2_io.Sampler, uri: str, export_settings: dict
    ):
        image = make_image(None, None, None, None, None, uri, export_settings)

        texture = gltf2_io.Texture(
            extensions=None, extras=None, name=None, sampler=sampler, source=image
        )

        return texture

    def set_texture_prop(self, name: str, index: int):
        """Set the texture based on the socket"""
        props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore

        node = ShaderUtils.get_texture_from_socket(
            name, self.shader.inputs[index], self.export_settings
        )

        if node is None or node.image is None:
            return False

        texture = ShaderTextureProperty(node.image.name)
        is_flash = texture.extension == "sc"

        prefix = props.path_prefix
        if (
            (prefix and texture)
            and not str(texture.path).startswith(prefix)
            and not is_flash
        ):
            texture = ShaderTextureProperty(
                (PurePath(prefix) / PurePath(texture.value)).as_posix()
            )
        elif is_flash and not str(texture.path).startswith("sc/"):
            texture = ShaderTextureProperty(
                (PurePath("sc/") / PurePath(texture.value)).as_posix()
            )

        # Kinda sus, but okay
        if node.extension != "CLIP":
            texture.keywords.append(node.extension.lower())

        texture_info = texture.value
        if props.legacy_materials:
            sampler = ShaderExporter.create_legacy_sampler(
                node.extension, node.interpolation, self.export_settings
            )

            texture_info = ShaderExporter.create_legacy_texture_info(
                sampler, texture_info, self.export_settings
            )

        self.sc_material.add_property(name, texture_info, ShaderTextureProperty)
        return True

    def set_color_prop(self, name: str, index: int):
        """Set the color based on the socket"""
        socket = self.shader.inputs[index]
        if ShaderUtils.is_color_socket(socket, name):
            self.sc_material.add_property(
                name, list(socket.default_value), ShaderFloatVectorProperty
            )
            return True

        return False

    def set_surface_color(
        self,
        name: str,
        tex_name: str,
        index: int,
        has_color: bool = True,
        **kwargs,
    ):
        valid_value = True
        valid_texture = self.set_texture_prop(tex_name, index)

        if has_color or not valid_texture:
            valid_value = self.set_color_prop(name, index)

            if not valid_texture and valid_value:
                valid_texture = True
                self.sc_material.add_property(
                    tex_name, [0.0, 0.0, 0.0, 1.0], ShaderFloatVectorProperty
                )

        if not valid_value and not valid_texture:
            valid_value = self.set_float_prop(name, index)
            valid_texture = True
            self.sc_material.add_property(
                tex_name, [0.0, 0.0, 0.0, 1.0], ShaderFloatVectorProperty
            )

        return valid_value or valid_texture

    def set_float_prop(self, name: str, index: int):
        """Set the float based on the socket"""
        socket = self.shader.inputs[index]
        if ShaderUtils.is_float_socket(socket, name):
            self.sc_material.add_property(
                name, socket.default_value, ShaderFloatProperty
            )
            return True

        return False

    def set_bool_prop(self, name: str, index: int):
        """Set the boolean based on the socket"""
        socket = self.shader.inputs[index]
        if ShaderUtils.is_bool_socket(socket, name):
            self.sc_material.add_property(
                name, socket.default_value, ShaderBooleanProperty
            )
            return True

        return False

    def set_custom_property(self, name: str, value: Any):
        prop_type = None
        if isinstance(value, bool):
            prop_type = ShaderBooleanProperty
        elif typing.is_typed_array(value, float):
            prop_type = ShaderFloatVectorProperty
        elif isinstance(value, float):
            prop_type = ShaderFloatProperty
        elif isinstance(value, Image):
            prop_type = ShaderTextureProperty
            sampler = ShaderExporter.create_legacy_sampler(
                "REPEAT", "LINEAR", self.export_settings
            )
            value = ShaderExporter.create_legacy_texture_info(
                sampler, str(PurePath(value.name).as_posix()), self.export_settings
            )

        if prop_type is None:
            print(
                f"Warning: Failed to guess SC IO shader type of custom property '{name}' with type {type(value)} in '{self.material.name}' material"
            )
            return False

        self.sc_material.add_property(name, value, prop_type)
        return True

    def export_modifiers(self):
        if "ScMultiplyModifier" in self.modifiers:
            self.sc_material.blend_mode = (
                ScBlendMode.SCREEN
            )  # TODO: Rename modifier and add support for the rest of blend modes

    def export_material(self):
        """Export the material to dictionary"""
        props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore
        self.sc_material.name = self.material.name

        # Export preset variables first
        self.preset.export_shader(self)

        # Export modifiers
        self.export_modifiers()

        # Then, export custom properties
        prop_keys = self.shader.keys()

        for key in prop_keys:
            # Handle constants which didn't make it into the shader
            if key == "$constants":
                if typing.is_typed_array(self.shader[key], str):
                    for constant in self.shader[key]:
                        self.sc_material.add_constant(constant)
                continue

            # Handle custom or unusual shader name
            if key == "$shader":
                if isinstance(self.shader[key], str):
                    self.sc_material.shader_name = self.shader[key]
                continue

            self.set_custom_property(key, self.shader[key])

        return (
            self.sc_material.to_dict()
            if props.legacy_materials
            else self.sc_material.to_typed_dict()
        )
