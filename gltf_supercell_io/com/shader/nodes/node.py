from bpy.types import ShaderNodeCustomGroup
from bpy.props import StringProperty
from ..loader import LibraryLoader


def update_tree(self, context):
    if not self.tree_id or self.tree_id == "":
        return

    tree = LibraryLoader.load_shader_tree(self.tree_id)
    self.node_tree = tree
    self.width = tree.default_group_node_width


class ShaderNodeScNode(ShaderNodeCustomGroup):
    bl_idname = "ShaderNodeScNode"
    bl_label = "Supercell IO Node"
    bl_icon = "NODE"

    tree_id: StringProperty(default="", update=update_tree)

    def copy(self, node):
        self.tree_id = node.tree_id
        self.node_tree = node.node_tree
        self.width = node.width
