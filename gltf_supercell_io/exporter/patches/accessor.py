from typing import TYPE_CHECKING

import bpy
import numpy as np
from io_scene_gltf2.blender.exp.primitive_attributes import __gather_attribute
from io_scene_gltf2.io.com.constants import ComponentType, DataType

from ...com.odin.attribute import OdinRawVertexAttribute
from ...com.odin.constants import OdinAttributeFormat, OdinAttributeType
from ...com.utilities.patcher import Patch

if TYPE_CHECKING:
    from ..ui import glTFSupercellExporterProperties


def gather_skins(blender_primitive, export_settings):
    """A bit optimized skins gather function for Odin purposes"""
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

            if (
                np.any(discarded_weights)
                and not export_settings["warning_joint_weight_exceed_already_displayed"]
            ):
                export_settings["log"].warning(
                    f"There are more than {influence_count} joint vertex influences. "
                    f"The {influence_count} with highest weight will be used (and normalized)."
                )
                export_settings["warning_joint_weight_exceed_already_displayed"] = True

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
    props: glTFSupercellExporterProperties = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore

    attributes = {}
    skin_done = False

    for name, attribute in blender_primitive["attributes"].items():
        skin_attribute = name.startswith(("JOINTS_", "WEIGHTS_"))

        if skin_attribute and skin_done is True:
            continue

        if name.startswith("MORPH_"):
            continue  # Target for morphs will be managed later

        odin_attribute = OdinAttributeType.from_attribute_name(name)
        if props.enabled and props.use_odin and odin_attribute is not None:
            if skin_attribute:
                attributes.update(gather_skins(blender_primitive, export_settings))
            else:
                # Creating special odin attribute proxy to retrieve and use in custom primitive hook
                # Do the same in gather_skins function
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
