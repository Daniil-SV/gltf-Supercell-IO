from abc import abstractmethod
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any, cast

import bpy
import numpy as np
from io_scene_gltf2.io.exp.binary_data import BinaryData

from ...com.odin.attribute import OdinMeshDataInfo

if TYPE_CHECKING:
    from io_scene_gltf2.blender.exp.tree import VExportTree
    from io_scene_gltf2.io.com.gltf2_io import (
        Animation,
        Gltf,
        Material,
        Mesh,
        Node,
        Skin,
    )

    from ..ui import glTFSupercellExporterProperties


def requires_extension(func):
    def wrapper(*args, **kwargs):
        cls = args[0]

        if cls.properties.enabled:
            func(*args, **kwargs)

    return wrapper


def requires_odin(func):
    def wrapper(*args, **kwargs):
        cls = args[0]

        if cls.properties.enabled and cls.properties.use_odin:
            func(*args, **kwargs)

    return wrapper


def to_dict(obj):
    if isinstance(obj, list):
        return [to_dict(sub) for sub in obj]

    if isinstance(obj, tuple):
        return (to_dict(sub) for sub in obj)

    if not hasattr(obj, "__dataclass_fields__"):
        return obj

    return {field.name: to_dict(getattr(obj, field.name)) for field in fields(obj)}


@dataclass
class PrimitiveData:
    attributes: dict
    indices: np.ndarray | Any | None
    mode: str | None
    material: bpy.types.Material | None
    targets: list | None


class glTF2BaseExporterComponent:
    def __init__(self, **kwargs):
        scene = cast(Any, bpy.context.scene)
        self.properties: glTFSupercellExporterProperties = (
            scene.glTFSupercellExporterProperties
        )

        # Buffer view with shared mesh properties
        # Should used as reference in all odin object
        # and filled with buffers at serialization stage
        self.odin_view = BinaryData(b"")

        self.vertex_descriptors: list[OdinMeshDataInfo] = []
        self.index_buffer: bytes = b""
        self.vertex_buffer: bytes = b""

    @abstractmethod
    def pre_export_hook(self, export_settings: dict):
        pass

    @abstractmethod
    def post_export_hook(self, export_settings: dict):
        pass

    @abstractmethod
    def gather_mesh_hook(
        self,
        gltf2_mesh: "Mesh",
        blender_mesh: bpy.types.Mesh,
        blender_object: bpy.types.Object,
        vertex_groups: bpy.types.VertexGroups | None,
        modifiers: bpy.types.ObjectModifiers | None,
        materials: tuple[bpy.types.Material],
        export_settings: dict,
    ):
        pass

    @abstractmethod
    def gather_material_hook(
        self,
        gltf2_material: "Material",
        blender_material: bpy.types.Material,
        export_settings: dict,
    ):
        pass

    @abstractmethod
    def vtree_before_filter_hook(self, vtree: "VExportTree", export_settings: dict):
        pass

    @abstractmethod
    def gather_joint_hook(self, node: Any, blender_bone: Any, export_settings: dict):
        pass

    @abstractmethod
    def gather_gltf_extensions_hook(self, gltf: "Gltf", export_settings: dict):
        """Note: This hook used after most of properties traversal. Last traverse will be executed at root extension property"""

    @abstractmethod
    def gather_attribute_change(
        self,
        attribute: str,
        data,
        is_normalized_byte_color: bool,
        export_settings: dict,
    ):
        pass

    @abstractmethod
    def gather_skin_hook(
        self,
        gltf2_skin: "Skin",
        blender_object: bpy.types.Object,
        export_settings: dict,
    ):
        pass

    @abstractmethod
    def gather_node_hook(
        self,
        gltf2_node: "Node",
        blender_object: bpy.types.Object,
        export_settings: dict,
    ):
        pass

    @abstractmethod
    def gather_primitive_hook(
        self,
        primitive: PrimitiveData,
        export_settings: dict,
    ):
        pass

    @abstractmethod
    def gather_gltf_hook(
        self,
        active_scene_idx: int,
        scenes,
        animations: list["Animation"],
        export_settings: dict,
    ):
        """Note: This hook used before any traversal operations and before animations/scenes handling"""
