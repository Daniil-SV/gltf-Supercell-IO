import bpy
from mathutils import Matrix
from typing import TYPE_CHECKING, cast
from .component import glTF2BaseImporterComponent, requires_extension
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
from io_scene_gltf2.io.com.constants import ComponentType, DataType

from io_scene_gltf2.io.exp.binary_data import BinaryData as ExportBinaryData
from io_scene_gltf2.blender.exp.accessors import gather_accessor

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import Skin
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter


class SkinImporter(glTF2BaseImporterComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.skin_idx = -1

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
