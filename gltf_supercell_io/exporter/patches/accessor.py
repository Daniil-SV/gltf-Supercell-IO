import bpy
import numpy as np
from ...com.utilities.patcher import Patch
from io_scene_gltf2.blender.exp.primitive_attributes import __gather_attribute
from ...com.odin.attribute import OdinRawVertexAttribute
from ...com.odin.constants import OdinAttributeType, OdinAttributeFormat
from io_scene_gltf2.io.com.constants import ComponentType, DataType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui import glTFSupercellExporterProperties

# def gather_skins(blender_primitive, export_settings):
#    attributes = {}
#
#    if not export_settings["gltf_skins"]:
#        return attributes
#
#    # Retrieve max set index
#    max_bone_set_index = 0
#    while blender_primitive["attributes"].get(
#        "JOINTS_" + str(max_bone_set_index)
#    ) and blender_primitive["attributes"].get("WEIGHTS_" + str(max_bone_set_index)):
#        max_bone_set_index += 1
#    max_bone_set_index -= 1
#
#    # Here, a set represents a group of 4 weights.
#    # So max_bone_set_index value:
#    # if -1 => No weights
#    # if 0 => Max 4 weights
#    # if 1 => Max 8 weights
#    # etc...
#
#    # If no skinning
#    if max_bone_set_index < 0:
#        return attributes
#
#    # Retrieve the wanted by user max set index
#    if export_settings["gltf_all_vertex_influences"]:
#        wanted_max_bone_set_index = max_bone_set_index
#    else:
#        wanted_max_bone_set_index = (
#            ceil(export_settings["gltf_vertex_influences_nb"] / 4) - 1
#        )
#
#    # No need to create a set with only zero if user asked more than requested group set.
#    if wanted_max_bone_set_index > max_bone_set_index:
#        wanted_max_bone_set_index = max_bone_set_index
#
#    # Set warning, for the case where there are more group of 4 weights needed
#    # Warning for the case where we are in the same group, will be done later
#    # (for example, 3 weights needed, but 2 wanted by user)
#    if max_bone_set_index > wanted_max_bone_set_index:
#        if export_settings["warning_joint_weight_exceed_already_displayed"] is False:
#            export_settings["log"].warning(
#                "There are more than {} joint vertex influences."
#                "The {} with highest weight will be used (and normalized).".format(
#                    export_settings["gltf_vertex_influences_nb"],
#                    export_settings["gltf_vertex_influences_nb"],
#                )
#            )
#            export_settings["warning_joint_weight_exceed_already_displayed"] = True
#
#        # Take into account only the first set of 4 weights
#        max_bone_set_index = wanted_max_bone_set_index
#
#    # Convert weights to numpy arrays, and setting joints
#    # weight_arrs = []
#    for s in range(0, max_bone_set_index + 1):
#
#        weight_id = f"WEIGHTS_{s}"
#        weight_odin_id = OdinAttributeType.from_attribute_name(weight_id)
#        if weight_odin_id is None:
#            continue
#
#        weight = blender_primitive["attributes"][weight_id]
#        weight = np.array(weight, dtype=np.float32)
#        weight = weight.reshape(len(weight) // 4, 4)
#
#        # Set warning for the case where we are in the same group, will be done later (for example, 3 weights needed, but 2 wanted by user)
#        # And then, remove no more needed weights
#        if (
#            s == max_bone_set_index
#            and not export_settings["gltf_all_vertex_influences"]
#        ):
#            # Check how many to remove
#            to_remove = (wanted_max_bone_set_index + 1) * 4 - export_settings[
#                "gltf_vertex_influences_nb"
#            ]
#            if to_remove > 0:
#                warning_done = False
#                for i in range(0, to_remove):
#                    idx = 4 - 1 - i
#                    if not all(weight[:, idx]):
#                        if warning_done is False:
#                            if (
#                                export_settings[
#                                    "warning_joint_weight_exceed_already_displayed"
#                                ]
#                                is False
#                            ):
#                                export_settings["log"].warning(
#                                    "There are more than {} joint vertex influences."
#                                    "The {} with highest weight will be used (and normalized).".format(
#                                        export_settings["gltf_vertex_influences_nb"],
#                                        export_settings["gltf_vertex_influences_nb"],
#                                    )
#                                )
#                                export_settings[
#                                    "warning_joint_weight_exceed_already_displayed"
#                                ] = True
#                            warning_done = True
#                    weight[:, idx] = 0.0
#
#        # joints
#        joint_id = "JOINTS_" + str(s)
#        joint_odin_id = OdinAttributeType.from_attribute_name(joint_id)
#        if joint_odin_id is None:
#            continue
#
#        internal_joint = blender_primitive["attributes"][joint_id]
#        component_type = ComponentType.UnsignedShort
#        if max(internal_joint) < 256:
#            component_type = ComponentType.UnsignedByte
#        joints = np.array(
#            internal_joint,
#            dtype=ComponentType.to_numpy_dtype(component_type),
#        )
#        joints = joints.reshape(-1, 4)
#
#        if (
#            s == max_bone_set_index
#            and not export_settings["gltf_all_vertex_influences"]
#        ):
#            # Check how many to remove
#            to_remove = (wanted_max_bone_set_index + 1) * 4 - export_settings[
#                "gltf_vertex_influences_nb"
#            ]
#            if to_remove > 0:
#                for i in range(0, to_remove):
#                    idx = 4 - 1 - i
#                    joints[:, idx] = 0.0
#
#        weight_total = weight.sum(axis=1).reshape(-1, 1)
#        attributes[weight_odin_id] = OdinRawVertexAttribute(
#            weight / weight_total, DataType.Vec4, ComponentType.Float
#        )
#
#        attributes[joint_odin_id] = OdinRawVertexAttribute(
#            joints, DataType.Vec4, component_type
#        )
#
#    return attributes


def gather_skins(blender_primitive, export_settings):
    attributes = {}

    if not export_settings["gltf_skins"]:
        return attributes

    attributes_data = blender_primitive["attributes"]

    weight_id = "WEIGHTS_0"
    joint_id = "JOINTS_0"

    weight_odin_id = OdinAttributeType.from_attribute_name(weight_id)
    joint_odin_id = OdinAttributeType.from_attribute_name(joint_id)

    if weight_odin_id is None or joint_odin_id is None:
        return attributes

    # Read weights
    weights = np.asarray(
        attributes_data[weight_id],
        dtype=np.float32,
    ).reshape(-1, 4)

    # Read joints
    internal_joints = attributes_data[joint_id]

    component_type = (
        ComponentType.UnsignedByte
        if max(internal_joints) < 256
        else ComponentType.UnsignedShort
    )

    joints = np.asarray(
        internal_joints,
        dtype=ComponentType.to_numpy_dtype(component_type),
    ).reshape(-1, 4)

    # Limit number of influences.
    if not export_settings["gltf_all_vertex_influences"]:
        influence_count = min(
            export_settings["gltf_vertex_influences_nb"],
            4,
        )

        if influence_count < 4:
            # Check whether any discarded influence has a non-zero weight.
            discarded_weights = weights[:, influence_count:]

            if np.any(discarded_weights):
                if not export_settings["warning_joint_weight_exceed_already_displayed"]:
                    export_settings["log"].warning(
                        "There are more than {} joint vertex influences. "
                        "The {} with highest weight will be used (and normalized).".format(
                            influence_count,
                            influence_count,
                        )
                    )
                    export_settings["warning_joint_weight_exceed_already_displayed"] = (
                        True
                    )

            weights[:, influence_count:] = 0.0
            joints[:, influence_count:] = 0

    # Normalize weights.
    weight_total = weights.sum(axis=1, keepdims=True)

    # Avoid division by zero for vertices without valid influences.
    np.divide(
        weights,
        weight_total,
        out=weights,
        where=weight_total != 0,
    )

    attributes[joint_odin_id] = OdinRawVertexAttribute(
        joints,
        DataType.Vec4,
        component_type,
        OdinAttributeFormat.from_components(DataType.Vec4, component_type),
    )

    attributes[weight_odin_id] = OdinRawVertexAttribute(
        weights,
        DataType.Vec4,
        ComponentType.Float,
        OdinAttributeFormat.from_components(DataType.Vec4, ComponentType.Float),
    )

    return attributes


def gather_primitive_attributes(blender_primitive, export_settings: dict):
    props: "glTFSupercellExporterProperties" = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore

    attributes = {}
    skin_done = False

    for name, attribute in blender_primitive["attributes"].items():
        skin_attribute = name.startswith("JOINTS_") or name.startswith("WEIGHTS_")

        if skin_attribute and skin_done is True:
            continue

        if name.startswith("MORPH_"):
            continue  # Target for morphs will be managed later

        odin_attribute = OdinAttributeType.from_attribute_name(name)
        if props.enabled and props.use_odin and odin_attribute is not None:
            if skin_attribute:
                attributes.update(gather_skins(blender_primitive, export_settings))
            else:
                attributes[odin_attribute] = OdinRawVertexAttribute(
                    attribute["data"],
                    attribute["data_type"],
                    attribute["component_type"],
                    OdinAttributeFormat.from_components(
                        attribute["data_type"], attribute["component_type"]
                    ),
                )
        else:
            attributes.update(
                __gather_attribute(blender_primitive, name, export_settings)
            )

        if skin_attribute:
            skin_done = True

    return attributes


primitive_gather_attribute = Patch(
    "array to accessor converter",
    module_path="io_scene_gltf2.blender.exp.primitive_attributes",
    target_method="gather_primitive_attributes",
    function=gather_primitive_attributes,
)
