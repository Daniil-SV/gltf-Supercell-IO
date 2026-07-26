import bpy

from pathlib import Path

from typing import TYPE_CHECKING, List
from .component import glTF2BaseImporterComponent, requires_extension

from ...com import glTF_extension_name, glTF_material_extension_name
from io_scene_gltf2.blender.imp.vnode import VNode

from io_scene_gltf2.io.com.gltf2_io import (
    Material,
    Scene,
    Animation,
    Skin,
)

if TYPE_CHECKING:
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
    from io_scene_gltf2.io.com.gltf2_io import (
        Accessor,
        Node,
    )
    from io_scene_gltf2.blender.imp.node import VNode


class CommonImporter(glTF2BaseImporterComponent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bone_nodes = set()

    def process_accessors(self, gltf: "glTFImporter"):
        """
        Supercell uses special component types for some accessors to optimize gpu memory usage,
        which is not standard and needs to be converted to normal here
        """
        # Exclusive Accessor Component Types
        # 1 - Float Vector 3
        # 2 - Float Vector 4
        # 3 - Matrix4x4

        accessors: List[Accessor] = gltf.data.accessors or []
        for accessor in accessors:
            accessor.component_type = accessor.component_type & 0x0000FFFF

    def move_materials(self, gltf: "glTFImporter"):
        """
        Supercell stores their updated materials in odin extension,
        and we need to move them to materials to simplify material handling
        so we can parse it from single predictable place
        """
        descriptor = self.get_extension(gltf)
        if descriptor is None:
            return

        materials = descriptor.get("materials")
        if materials is None:
            return

        gltf.data.materials = [
            Material.from_dict({"extensions": {glTF_material_extension_name: material}})
            for material in materials
        ]

    def process_nodes(self, gltf: "glTFImporter"):
        """
        Repairs gltf children relation indexing based on classic parent indexing stored in node extensions
        """

        nodes: List["Node"] = gltf.data.nodes or []

        childrens: dict[int, list[int]] = {}

        def add_child(idx: int, parent_idx: int):
            if parent_idx not in childrens:
                childrens[parent_idx] = []
            childrens[parent_idx].append(idx)

        for i, node in enumerate(nodes):
            extensions = node.extensions
            if extensions is None:
                continue

            descriptor = extensions.get(glTF_extension_name)
            if descriptor is None:
                continue

            parent = descriptor.get("parent")
            add_child(i, parent)

        for idx, children in childrens.items():
            nodes[idx].children = children

    def get_selected_armature_bones(self):
        """
        Returns list of bone names of currently selected armatures
        Used for animation bones recovery
        """
        ctx = bpy.context
        layer = ctx.view_layer
        if layer is None:
            return

        selected = [obj for obj in ctx.selected_objects if obj.type == "ARMATURE"]
        if len(selected) == 0:
            return

        result: set[str] = set()
        for obj in selected:
            if not isinstance(obj.data, bpy.types.Armature):
                continue

            result.update([bone.name for bone in obj.data.bones])

        return list(result)

    def restore_skin_bones(self, gltf: "glTFImporter"):
        skins: list[Skin] = gltf.data.skins or []
        for i, skin in enumerate(skins):
            joints: list[int] = skin.joints or []

            def visit(idx: int):
                node: "Node" = gltf.data.nodes[idx]
                node.skin = i

                if node.name:
                    self.bone_nodes.add(node.name)

                for children in node.children or []:
                    visit(children)

            for joint in joints:
                visit(joint)

    def do_final_fixups(self, gltf: "glTFImporter"):
        """
        Very often Supercell glTF files have missing fields that are required by the importer,
        this function adds them back
        """

        root_nodes = []
        nodes: List["Node"] = gltf.data.nodes or []
        skins = gltf.data.skins = gltf.data.skins or []

        # Fix for scene and root nodes definition
        if gltf.data.scenes is None:
            childrens = set()
            for node in nodes:
                if node.children is None:
                    continue

                childrens.update(node.children)

            root_nodes = [i for i in range(len(nodes)) if i not in childrens]
            gltf.data.scenes = [Scene(None, None, None, root_nodes)]
        else:
            for scene in gltf.data.scenes:
                if scene.nodes is not None:
                    root_nodes = scene.nodes
                    break

        if gltf.data.scene is None:
            gltf.data.scene = 0

        # Some of root nodes may has scale(0, 0, 0) for some fucking reason
        # Which is obviously wrong and which is cause for bones calculation errors later
        for node_idx in root_nodes:
            node: "Node" = gltf.data.nodes[node_idx]
            if node.scale == [0, 0, 0]:
                node.scale = None

        bone_names = None
        if self.properties.apply_animation:
            bone_names = self.get_selected_armature_bones()

        is_embedded_animation = (
            len(gltf.data.meshes or []) != 0 and len(gltf.data.animations or []) != 0
        )
        is_static_scene = (
            len(gltf.data.animations or []) == 0 and len(skins) == 0 and not bone_names
        )
        if (
            self.properties.single_skeleton
            and not is_embedded_animation
            and not is_static_scene
        ):
            # Most of animations doesn't have actual skin
            # We should create placeholder one, so blender could process it properly
            # not as empties
            if len(skins) == 0:
                joints = [
                    i
                    for i, node in enumerate(gltf.data.nodes)
                    if node.mesh is None  # node is mesh reference
                    and node.camera is None  # node is camera references
                    and node.skin is None  # node has explicit skin index
                    and (
                        True if bone_names is None else node.name in bone_names
                    )  # Optionally, we could restore it from selected armature
                ]

                skins.append(Skin.from_dict({"joints": joints}))
            else:
                self.restore_skin_bones(gltf)

            if len(root_nodes) == 1:
                for skin in skins:
                    skin.skeleton = root_nodes[0]
            else:
                children_mapping = {key: [] for key in root_nodes}

                def visit(key: int, node_index: int):
                    childrens = gltf.data.nodes[node_index].children or []

                    for idx in childrens:
                        children_mapping[key].append(idx)
                        visit(key, idx)

                for key in root_nodes:
                    visit(key, key)

                for skin in skins:
                    for key, childrens in children_mapping.items():
                        if any(i in childrens for i in skin.joints or []):
                            skin.skeleton = key
                            break

        gltf.data.meshes = gltf.data.meshes or []

    def setup_settings(self, gltf: "glTFImporter"):
        # Why tf this exists at all
        gltf.import_settings["disable_bone_shape"] = True

        # May have other values in some older versions
        gltf.import_settings["bone_heuristic"] = "BLENDER"

        # Also very useful thing for mesh
        gltf.import_settings["merge_vertices"] = True

        # This option breaks some meshes sometime
        # Looks useful for some cases, but... not sure if it's worth to have it enabled by default
        gltf.import_settings["guess_original_bind_pose"] = False

    def move_animation(self, gltf: "glTFImporter"):
        """
        Supercell also stores animations in odin extension,
        so they also need to be moved to the animations for proper processing.
        Only one action per file is possible with odin
        Even if source file contained multiple actions, they are combined to single animation definition
        """
        descriptor = self.get_extension(gltf)
        if descriptor is None:
            return

        animation = descriptor.get("animation")
        if animation is None:
            return

        name = Path(gltf.filename).stem
        animations = gltf.data.animations = gltf.data.animations or []
        animations.append(
            Animation([], {glTF_extension_name: animation}, None, name, [])
        )

    @requires_extension
    def gather_import_gltf_before_hook(self, gltf):
        self.process_accessors(gltf)
        self.move_materials(gltf)
        self.move_animation(gltf)

        self.process_nodes(gltf)
        self.do_final_fixups(gltf)

        if self.properties.better_settings:
            self.setup_settings(gltf)

        # Shared cache for all meshes import operations
        gltf.supercell_vertex_cache = {}  # type: ignore
        gltf.supercell_vertex_accessor_offset = 0  # type: ignore

    @requires_extension
    def gather_import_node_before_hook(self, vnode, node, gltf):
        if node is None:
            return

        # Some nodes (especially in animation files) may have invalid indices,
        # we need to clean them up to avoid errors
        meshes_count = len(gltf.data.meshes or [])
        if node.mesh is not None:
            if node.mesh >= meshes_count:
                node.mesh = None
                vnode.type = VNode.DummyRoot
                vnode.mesh_node_idx = None

    @requires_extension
    def gather_import_scene_after_nodes_hook(self, gltf_scene, blender_scene, gltf):
        if self.properties.adjust_colorspace:
            blender_scene.view_settings.view_transform = "Raw"  # type: ignore
