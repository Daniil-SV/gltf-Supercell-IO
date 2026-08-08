import bpy
from typing import TYPE_CHECKING, cast, Any, Protocol
from ...com import glTF_extension_name, glTF_material_extension_name
from abc import abstractmethod

if TYPE_CHECKING:
    from ..ui import glTFSupercellImporterProperties
    from io_scene_gltf2.blender.imp.vnode import VNode
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
    from io_scene_gltf2.io.com.gltf2_io import Material, Node, Mesh, Scene, Accessor
    from io_scene_gltf2.io.imp.user_extensions import MutatingArgument


class IMPORT_mesh_options(Protocol):
    skinning = True
    skin_into_bind_pose = True


def is_valid_scgltf(gltf: "glTFImporter"):
    """Returns True if gltf is valid Supercell glTF and is subject to further processing"""
    required = gltf.data.extensions_required or []
    used = gltf.data.extensions_used or []
    has_extension = glTF_extension_name in required
    has_shader = glTF_material_extension_name in used

    # Sometimes extensions is empty, but we still need to know if it's Supercell glTF
    # So, try to look for extension descriptor
    if not has_extension and not has_shader and gltf.data.materials:
        material = gltf.data.materials[0]
        has_shader = (
            material.extensions is not None
            and glTF_material_extension_name in material.extensions
        )

    return has_extension or has_shader


def requires_extension(func):
    def wrapper(*args, **kwargs):
        # gltf always last in arguments array
        gltf: "glTFImporter" = args[len(args) - 1]

        if is_valid_scgltf(gltf):
            func(*args, **kwargs)

    return wrapper


class glTF2BaseImporterComponent:
    def __init__(self, **kwargs):
        scene = cast(Any, bpy.context.scene)
        self.properties: glTFSupercellImporterProperties = (
            scene.glTFSupercellImporterProperties
        )

    def get_extension(self, gltf: "glTFImporter") -> dict | None:
        """Returns SC_odin_format extension descriptor, if exists, otherwise returns None"""
        extensions: dict = gltf.data.extensions
        if extensions is None:
            return None

        return extensions.get(glTF_extension_name, None)

    @abstractmethod
    def gather_import_gltf_before_hook(self, gltf: "glTFImporter"):
        pass

    @abstractmethod
    def gather_import_mesh_options(
        self,
        mesh_options: IMPORT_mesh_options,
        pymesh: "Mesh",
        skin_idx: int,
        gltf: "glTFImporter",
    ):
        pass

    @abstractmethod
    def gather_import_animation_before_hook(self, anim_idx: int, gltf: "glTFImporter"):
        pass

    @abstractmethod
    def gather_import_material_before_hook(
        self, gltf_material: "Material", vertex_color: str, gltf: "glTFImporter"
    ):
        pass

    @abstractmethod
    def gather_import_material_after_hook(
        self,
        gltf_material: "Material",
        vertex_color: str,
        blender_mat: bpy.types.Material,
        gltf: "glTFImporter",
    ):
        pass

    @abstractmethod
    def gather_import_scene_after_nodes_hook(
        self, gltf_scene: "Scene", blender_scene: bpy.types.Scene, gltf: "glTFImporter"
    ):
        pass

    @abstractmethod
    def gather_import_node_before_hook(
        self, vnode: "VNode", node: "Node | None", gltf: "glTFImporter"
    ):
        pass

    @abstractmethod
    def gather_import_mesh_after_hook(
        self, gltf_mesh: "Mesh", blender_mesh: bpy.types.Mesh, gltf: "glTFImporter"
    ):
        pass

    @abstractmethod
    def gather_import_scene_after_animation_hook(
        self,
        gltf_scene: "Scene | None",
        blender_scene: bpy.types.Scene,
        gltf: "glTFImporter",
    ):
        pass

    @abstractmethod
    def decode_accessor_before_hook(
        self,
        accessor: "Accessor",
        array: "MutatingArgument",
        gltf: "glTFImporter",
    ):
        pass
