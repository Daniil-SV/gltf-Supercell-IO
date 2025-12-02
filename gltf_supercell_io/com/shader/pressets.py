import bpy
import os
from bpy.types import ShaderNodeGroup, ShaderNodeTexImage, ShaderNodeOutputMaterial
from typing import Tuple
from enum import StrEnum
from ..materials import ScShaderMaterial, ScBlendMode
from ..materials.variables import ShaderFloatVectorProperty, ShaderFloatProperty, ShaderTextureProperty, ShaderProperty


class ShaderPresetType(StrEnum):
    UNLIT = "Unlit"
    BRAWL_STARS = "BrawlStars"


class ShaderPreset:
    LibraryName = "SupercellIO"
    BaseDirectory = os.path.dirname(os.path.abspath(__file__))
    LibraryPath = os.path.join(
        BaseDirectory, "library", "supercell_io_shaders.blend")

    def __init__(self, sc_material: ScShaderMaterial, material: bpy.types.Material):
        self.sc_material = sc_material
        self.material = material
        self.shader: ShaderNodeGroup = None
        self.node_counter = 0

    def create_material(self):
        tree = self.material.node_tree
        self.setup_blending()

        output: ShaderNodeOutputMaterial = tree.nodes.new(
            'ShaderNodeOutputMaterial'
        )
        output.location = 200, 100

        self.create_shader()
        tree.links.new(output.inputs[0], self.shader.outputs[0])

        self.shader["$constants"] = self.sc_material.unused_constants
        for variable in self.sc_material.unused_variables:
            self.set_raw_shader_prop(variable)

    def setup_blending(self):
        if self.sc_material.blend_mode == ScBlendMode.Opaque:
            self.material.surface_render_method = 'DITHERED'
        else:
            self.material.surface_render_method = 'BLENDED'
            
    def set_raw_shader_prop(self, raw_property: Tuple[str, ShaderProperty]):
        key, prop = raw_property
        if (isinstance(raw_property, ShaderNodeTexImage)):
            # TODO: Add image conversion ?
            self.shader[key] = prop.texture_path
        else:
            self.shader[key] = prop.value
            

    def set_constant_prop(self, name: str, index: int):
        socket = self.shader.inputs[index]
        socket.default_value = self.sc_material.has_constant(name)

    def set_texture_prop(self, name: str, index: int):
        prop: ShaderTextureProperty = self.sc_material.get_property(
            name, ShaderTextureProperty
        )

        node: ShaderNodeTexImage = self.material.node_tree.nodes.new(
            "ShaderNodeTexImage"
        )

        x, y = self.shader.location

        # Base horizontal offset
        x -= 465

        # Vertical offset based on current node count and number
        if (self.node_counter and self.node_counter % 3 == 0):
            x -= 200
            y += (self.node_counter / 2) * 110
        else:
            y += self.node_counter * 110

        node.location = x, y
        node.extension = "REPEAT" if "repeat" in prop.keywords else "CLIP"
        self.material.node_tree.links.new(
            self.shader.inputs[index], node.outputs[0])
        self.node_counter += 1

    def set_color_prop(self, name: str, index: int):
        prop: ShaderFloatVectorProperty = self.sc_material.get_property(
            name, ShaderFloatVectorProperty
        )

        if (prop is None):
            return

        socket = self.shader.inputs[index]
        socket.default_value = prop.vector

    def set_float_prop(self, name: str, index: int):
        prop: ShaderFloatProperty = self.sc_material.get_property(
            name, ShaderFloatProperty
        )

        if (prop is None):
            return

        socket = self.shader.inputs[index]
        socket.default_value = prop.number

    def instantiate_shader(self, id: str, name: str) -> ShaderNodeGroup:
        asset = bpy.data.node_groups.get(id)
        if (asset is None):
            with bpy.data.libraries.load(ShaderPreset.LibraryPath, link=True, assets_only=True) as (data_from, data_to):
                data_to.node_groups = [id]

            asset = bpy.data.node_groups.get(id)
            if asset is None:
                raise ImportError("Failed to instantiate Supercell IO shader")

        shader: ShaderNodeGroup = self.material.node_tree.nodes.new(
            "ShaderNodeGroup"
        )
        shader.node_tree = asset
        shader.label = name
        shader.location = 40 - asset.default_group_node_width, 100
        shader.width = asset.default_group_node_width

        return shader

    def create_shader(self) -> ShaderNodeGroup:
        raise NotImplementedError()
