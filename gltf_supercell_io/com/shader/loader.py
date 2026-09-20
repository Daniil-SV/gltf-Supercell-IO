import os
from typing import TYPE_CHECKING

import bpy
from bpy.types import ShaderNodeTree

if TYPE_CHECKING:
    from .nodes import ShaderNodeScNode, ShaderNodeScShader, ShaderNodeScUtility


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
                _data_from,
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
        shader: ShaderNodeScNode = node_tree.nodes.new(
            type_id
        )  # ty: ignore[invalid-assignment]
        shader.tree_id = tree_id
        return shader

    @staticmethod
    def instantiate_utility(
        node_tree: ShaderNodeTree, tree_id: str
    ) -> "ShaderNodeScUtility":
        return LibraryLoader.instantiate_node("ShaderNodeScUtility", node_tree, tree_id)

    @staticmethod
    def instantiate_shader(
        node_tree: ShaderNodeTree, tree_id: str
    ) -> "ShaderNodeScShader":
        shader: ShaderNodeScShader = LibraryLoader.instantiate_node(
            "ShaderNodeScShader", node_tree, tree_id
        )
        shader.preset_id = tree_id

        return shader
