import bpy
from typing import TYPE_CHECKING, cast, Any
from abc import abstractmethod

if TYPE_CHECKING:
    from ..ui import glTFSupercellExporterProperties
    from io_scene_gltf2.io.com.gltf2_io import Gltf
    from io_scene_gltf2.io.com.gltf2_io import Material, Mesh
    from io_scene_gltf2.blender.exp.tree import VExportTree


class glTF2BaseExporterComponent:
    def __init__(self, **kwargs):
        scene = cast(Any, bpy.context.scene)
        self.properties: glTFSupercellExporterProperties = (
            scene.glTFSupercellExporterProperties
        )

    @abstractmethod
    def pre_export_hook(self, export_settings: dict):
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
        pass
