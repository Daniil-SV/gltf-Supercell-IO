import bpy
from mathutils import Matrix, Vector

from io_scene_gltf2.blender.exp.accessors import gather_accessor
from io_scene_gltf2.io.exp.binary_data import BinaryData
from io_scene_gltf2.io.com.constants import ComponentType, DataType
from ...com.utilities.patcher import Patch


def inverse_bind_matrices_hook(armature_uuid: str, export_settings: dict = {}):
    blender_armature_object = (
        export_settings["vtree"].nodes[armature_uuid].blender_object
    )

    axis_basis_change = Matrix.Identity(4)
    if export_settings["gltf_yup"]:
        axis_basis_change = Matrix(
            (
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, -1.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )
        )

    # store matrix_world of armature in case we need to add a neutral bone
    export_settings["vtree"].nodes[
        armature_uuid
    ].matrix_world_armature = blender_armature_object.matrix_world.copy()

    bones_uuid = export_settings["vtree"].get_all_bones(armature_uuid)

    def __collect_matrices(bone: bpy.types.PoseBone):
        scale = Vector((1.0, 1.0, 1.0))
        scaleOverride: list[float] = bone.get("scScaleOverride")
        if scaleOverride is not None:
            scale = Vector(scaleOverride)

        inverse_bind_matrix = (
            axis_basis_change
            @ (blender_armature_object.matrix_world @ bone.bone.matrix_local)
            @ Matrix.Diagonal((*scale, 1.0))
        ).inverted_safe()
        matrices.append(inverse_bind_matrix)

    matrices = []
    for b in bones_uuid:
        if export_settings["vtree"].nodes[b].leaf_reference is None:
            __collect_matrices(
                blender_armature_object.pose.bones[
                    export_settings["vtree"].nodes[b].blender_bone.name
                ]
            )
        else:
            inverse_bind_matrix = (
                axis_basis_change
                @ (
                    blender_armature_object.matrix_world
                    @ export_settings["vtree"]
                    .nodes[export_settings["vtree"].nodes[b].leaf_reference]
                    .matrix_world_tail
                )
            ).inverted_safe()
            matrices.append(inverse_bind_matrix)  # Leaf bone

    # flatten the matrices
    inverse_matrices = []
    for matrix in matrices:
        for column in range(0, 4):
            for row in range(0, 4):
                inverse_matrices.append(matrix[row][column])

    binary_data = BinaryData.from_list(inverse_matrices, ComponentType.Float)

    major, minor, _ = bpy.app.version
    if major >= 5 and minor >= 2:
        return gather_accessor(
            binary_data,
            ComponentType.Float,
            len(inverse_matrices) // DataType.num_elements(DataType.Mat4),
            None,
            None,
            DataType.Mat4,  # type: ignore
            None,
            export_settings,
        )
    else:
        return gather_accessor(
            binary_data,
            ComponentType.Float,
            len(inverse_matrices) // DataType.num_elements(DataType.Mat4),
            None,
            None,
            DataType.Mat4,  # type: ignore
            export_settings,
        )


inverse_bind_matrices_gather = Patch(
    "inverse bind matrices export",
    module_path="io_scene_gltf2.blender.exp.skins",
    target_method="__gather_inverse_bind_matrices",
    function=inverse_bind_matrices_hook,
)
