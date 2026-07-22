import bpy
import os

from bpy.types import ShaderNodeTree
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .nodes import ShaderNodeScNode, ShaderNodeScUtility, ShaderNodeScShader


class LibraryLoader:
    BaseDirectory = os.path.dirname(os.path.abspath(__file__))
    LibraryName = "supercell_io_shaders.blend"
    LibraryPath = os.path.join(BaseDirectory, "library", LibraryName)

    @staticmethod
    def load_shader_tree(id: str) -> ShaderNodeTree:
        asset = bpy.data.node_groups.get(id)
        if asset is None:
            with bpy.data.libraries.load(
                LibraryLoader.LibraryPath, link=True, assets_only=True
            ) as (  # type: ignore
                data_from,
                data_to,
            ):
                data_to.node_groups = [id]

            asset = bpy.data.node_groups.get(id)
            if asset is None:
                raise ImportError("Failed to instantiate Supercell IO shader")

        if not isinstance(asset, ShaderNodeTree):
            raise TypeError("Loaded asset is not a ShaderNodeTree")

        return asset

    @staticmethod
    def instantiate_node(type_id: str, node_tree: ShaderNodeTree, tree_id: str):
        shader: ShaderNodeScNode = node_tree.nodes.new(type_id)  # type: ignore # noqa
        shader.tree_id = tree_id

        return shader

    @staticmethod
    def instantiate_utility(
        node_tree: ShaderNodeTree, tree_id: str
    ) -> "ShaderNodeScUtility":
        return LibraryLoader.instantiate_node("ShaderNodeScUtility", node_tree, tree_id)  # type: ignore # noqa

    @staticmethod
    def instantiate_shader(
        node_tree: ShaderNodeTree, tree_id: str
    ) -> "ShaderNodeScShader":
        shader: ShaderNodeScShader = LibraryLoader.instantiate_node(
            "ShaderNodeScShader", node_tree, tree_id
        )  # type: ignore # noqa
        shader.preset_id = tree_id

        return shader
