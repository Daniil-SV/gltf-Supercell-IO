import bpy
from mathutils import Vector
from typing import TYPE_CHECKING, Any
from .component import glTF2BaseImporterComponent, requires_extension
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
from io_scene_gltf2.io.com.constants import ComponentType, DataType

from io_scene_gltf2.io.exp.binary_data import BinaryData as ExportBinaryData
from io_scene_gltf2.blender.exp.accessors import gather_accessor
from io_scene_gltf2.blender.imp.vnode import VNode

if TYPE_CHECKING:
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
    from io_scene_gltf2.io.com.gltf2_io import Skin, Node, Scene


class SkinImporter(glTF2BaseImporterComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.skin_idx = -1
        self.noop_joints: set[int] = set()

    def valid_skin(self, skin: "Skin"):
        # Check if skin has duplicate joints indices
        # This is the reason to completely rebuild skin
        # Since this may cause problems like invalid vertex groups or bind pose miscalculation
        joints: list[int] = skin.joints or []
        unique_joints = set()
        duplicate_joints = set(
            x for x in joints if x in unique_joints or unique_joints.add(x)
        )

        if len(duplicate_joints) != 0:
            return False

        return True

    @requires_extension
    def gather_import_mesh_options(
        self,
        mesh_options,
        pymesh,
        skin_idx,
        gltf,
    ):
        # Need to save skin idx to properly fix skin in mesh after hook
        self.skin_idx = skin_idx

    def merge_vertex_groups(
        self,
        vertices: bpy.types.MeshVertices,
        groups: bpy.types.VertexGroups,
        idx_a: int,
        idx_b: int,
    ):
        group_a = groups[idx_a]
        group_b = groups[idx_b]

        for vert in vertices:
            weight_a = 0.0
            weight_b = 0.0

            for g in vert.groups:
                if g.group == group_a.index:
                    weight_a = g.weight
                elif g.group == group_b.index:
                    weight_b = g.weight

            if weight_b > 0.0:
                group_a.add([vert.index], weight_a + weight_b, "REPLACE")

    def remove_vertex_groups(
        self, groups: bpy.types.VertexGroups, group_indices: list[int]
    ):
        for index in sorted(set(group_indices), reverse=True):
            groups.remove(groups[index])

    @requires_extension
    def gather_import_mesh_after_hook(self, gltf_mesh, blender_mesh, gltf):
        if self.skin_idx is None or self.skin_idx == -1:
            return

        skins: list["Skin"] = gltf.data.skins or []
        target_skin = skins[self.skin_idx]
        joints = target_skin.joints or []
        if self.valid_skin(target_skin):
            return

        tmp_ob = bpy.data.objects.new("##gltf-import:tmp-object##", blender_mesh)
        groups = tmp_ob.vertex_groups
        vertices = tmp_ob.data.vertices  # type: ignore

        duplicate_indices = []
        unique_indices = set()
        for idx, joint_index in enumerate(joints):
            if joint_index not in unique_indices:
                unique_indices.add(joint_index)
                continue

            duplicate_indices.append(idx)
            self.merge_vertex_groups(vertices, groups, joints.index(joint_index), idx)

        self.remove_vertex_groups(groups, duplicate_indices)

    @requires_extension
    def gather_import_gltf_before_hook(self, gltf):
        nodes: list["Node"] = gltf.data.nodes or []
        skins: list["Skin"] = gltf.data.skins or []

        parents: dict[int, int | None] = {}

        def visit_scene(idx: int, parent_idx: int | None):
            node = nodes[idx]
            if node.mesh is not None:
                return

            parents[idx] = parent_idx
            for children in node.children or []:
                visit_scene(children, idx)

        scenes: list["Scene"] = gltf.data.scenes
        for scene in scenes or []:
            for idx in scene.nodes or []:
                visit_scene(idx, None)

        def visit_skin(idx: int):
            if idx not in parents:
                return

            parent = parents[idx]
            del parents[idx]

            if parent is None:
                return
            visit_skin(parent)

        for skin in skins:
            for idx in skin.joints or []:
                visit_skin(idx)

        for skin in skins:
            added_joints = 0
            joints: list[int] = skin.joints or []
            inv_binds: list[list[float]] = []
            if skin.inverse_bind_matrices is not None:
                inv_binds = BinaryData.get_data_from_accessor(
                    gltf, skin.inverse_bind_matrices
                )

            def visit(idx: int, accum: int):
                node = nodes[idx]
                if idx in parents:
                    accum += 1
                    inv_binds.append([1.0 if i % 5 == 0 else 0.0 for i in range(16)])
                    joints.append(idx)
                    self.noop_joints.add(idx)
                    del parents[idx]

                for children in node.children or []:
                    accum = visit(children, accum)

                return accum

            for idx in joints:
                added_joints = visit(idx, added_joints)

            if added_joints == 0:
                continue

            skin.joints = joints
            if skin.inverse_bind_matrices is None:
                continue

            binary_data = ExportBinaryData.from_list(
                [value for matrix in inv_binds for value in matrix], ComponentType.Float
            )
            new_accessor = gather_accessor(
                binary_data,
                ComponentType.Float,
                len(inv_binds) // DataType.num_elements(DataType.Mat4),
                None,
                None,
                DataType.Mat4,  # type: ignore
                {},
            )

            skin.inverse_bind_matrices = len(gltf.data.accessors)
            gltf.data.accessors.append(new_accessor)

    def filter_deform_bones(self, gltf: "glTFImporter"):
        vnodes: dict[Any, VNode] = gltf.vnodes  # type: ignore

        deform_bones: list[int] = []
        skins: list[Skin] = gltf.data.skins or []

        # Create list of deform bones
        for skin in skins:
            deform_bones += skin.joints or []

        # Set use_deform for each armature and bone
        def visit(vnode_id: Any):
            vnode: VNode = vnodes[vnode_id]

            if vnode.type == VNode.Bone:
                bone_arma = vnode.bone_arma  # type: ignore
                arma_object: bpy.types.Object = vnodes[bone_arma].blender_object  # type: ignore
                armature: bpy.types.Armature = arma_object.data  # type: ignore

                bone_name = vnode.blender_bone_name  # type: ignore
                bone: bpy.types.Bone = armature.bones[bone_name]  # type: ignore
                bone.use_deform = (
                    vnode_id in deform_bones and vnode_id not in self.noop_joints
                )

            for children in vnode.children:
                visit(children)

        visit("root")

    def move_pose_bone_offset(self, bone: bpy.types.PoseBone):
        default_scale = Vector((1.0, 1.0, 1.0))
        if bone.scale != default_scale:
            bone["scScaleOverride"] = bone.scale
            bone.scale = default_scale

    def create_pose_bones_properties(self, gltf: "glTFImporter"):
        """
        This function iterates over created gltf bones and moves pose mode transformation to custom properties
        This is required for correct displaying in blender and for correct inverse matrices exporting
        """
        vnodes: dict[Any, VNode] = gltf.vnodes  # type: ignore

        def visit(vnode_id: Any, armature: bpy.types.Object):
            vnode: VNode = vnodes[vnode_id]

            if vnode.type == VNode.Bone:
                bone_name = vnode.blender_bone_name  # type: ignore
                if armature.pose and armature.pose.bones[bone_name]:
                    bone = armature.pose.bones[bone_name]
                    self.move_pose_bone_offset(bone)

            for children in vnode.children:
                visit(children, armature)

        for vnode in vnodes.values():
            if vnode.type != VNode.Object and not vnode.is_arma:
                continue

            armature: bpy.types.Object = vnode.blender_object  # type: ignore
            for children in vnode.children:
                visit(children, armature)

    @requires_extension
    def gather_import_scene_after_nodes_hook(self, gltf_scene, blender_scene, gltf):
        self.filter_deform_bones(gltf)
        self.create_pose_bones_properties(gltf)
