from bpy.types import (
    NodeSocket,
    NodeSocketColor,
    NodeSocketFloatFactor,
    NodeSocketFloat,
    NodeSocketBool,
)
from bpy.types import Material, ShaderNodeTree, ShaderNodeTexImage
from typing import TypeGuard
from io_scene_gltf2.blender.exp.material.search_node_tree import (
    NodeSocket as SocketWrapper,
    NodeTreeSearchResult,
    get_texture_node_from_socket,
)


class ShaderUtils:
    @staticmethod
    def is_texture_socket(socket: NodeSocket, name: str) -> TypeGuard[NodeSocketColor]:
        if not isinstance(socket, NodeSocketColor) and not isinstance(
            socket, NodeSocketFloatFactor
        ):
            print(
                f"Warning: Failed to get texture prop socket in SC IO shader for {name}"
            )
            return False

        return True

    @staticmethod
    def is_color_socket(socket: NodeSocket, name: str) -> TypeGuard[NodeSocketColor]:
        if not isinstance(socket, NodeSocketColor):
            print(
                f"Warning: Failed to get color prop socket in SC IO shader for {name}"
            )
            return False

        return True

    @staticmethod
    def is_float_socket(socket: NodeSocket, name: str) -> TypeGuard[NodeSocketFloat]:
        if not isinstance(socket, NodeSocketFloatFactor) and not isinstance(
            socket, NodeSocketFloat
        ):
            print(
                f"Warning: Failed to get float prop socket in SC IO shader for {name}"
            )
            return False

        return True

    @staticmethod
    def is_bool_socket(socket: NodeSocket, name: str) -> TypeGuard[NodeSocketBool]:
        if not isinstance(socket, NodeSocketBool):
            print(
                f"Warning: Failed to get boolean prop socket in SC IO shader for {name}"
            )
            return False

        return True

    @staticmethod
    def get_node_tree(material: Material) -> ShaderNodeTree:
        if not material.use_nodes:
            material.use_nodes = True

        tree = material.node_tree
        if tree is None:
            raise RuntimeError("Failed to get node tree from material")

        return tree

    @staticmethod
    def get_texture_from_socket(name: str, socket: NodeSocket, export_settings: dict):
        """Set the texture based on the socket"""
        node_socket = SocketWrapper(socket, [])
        if not ShaderUtils.is_texture_socket(socket, name):
            return

        texture_socket: NodeTreeSearchResult | None = get_texture_node_from_socket(
            node_socket, export_settings
        )

        if texture_socket is None or not isinstance(
            texture_socket.shader_node, ShaderNodeTexImage
        ):
            # Socket has no textures connected, return
            return

        return texture_socket.shader_node
