import bpy
from .node import ShaderNodeScNode


class ShaderNodeScShader(ShaderNodeScNode):
    bl_idname = "ShaderNodeScShader"
    bl_label = "Supercell IO Shader"
    bl_icon = "SHADERFX"

    preset_id: bpy.props.StringProperty(default="")

    def copy(self, node):
        super().copy(node)
        self.preset_id = node.preset_id
