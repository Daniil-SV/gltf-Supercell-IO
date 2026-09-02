import bpy
from typing import TYPE_CHECKING, Optional

from io_scene_gltf2.blender.exp.accessors import (
    gather_accessor as base_gather_accessor,
    array_to_accessor as base_array_to_accessor,
)

if TYPE_CHECKING:
    from io_scene_gltf2.io.exp.binary_data import BinaryData
    from io_scene_gltf2.io.com.constants import ComponentType, DataType
    from io_scene_gltf2.io.com.gltf2_io import Accessor


def array_to_accessor(
    attribute_name,
    array,
    export_settings,
    component_type,
    data_type,
    include_max_and_min=False,
    sparse_type=None,
    normalized=None,
):
    major, minor, _ = bpy.app.version
    if major >= 5 and minor >= 2:
        return base_array_to_accessor(
            attribute_name,
            array,
            export_settings,
            component_type,
            data_type,
            include_max_and_min,
            sparse_type,
            normalized,
        )
    else:
        return base_array_to_accessor(
            array,
            export_settings,
            component_type,
            data_type,
            include_max_and_min,
            sparse_type,  # type: ignore
            normalized,
        )


def gather_accessor(
    buffer_view: "BinaryData",
    component_type: "ComponentType",
    count: Optional[int],
    max: Optional[int],
    min: Optional[int],
    type: "DataType",
    export_settings: dict,
) -> "Accessor":
    major, minor, _ = bpy.app.version
    if major >= 5 and minor >= 2:
        return base_gather_accessor(
            buffer_view,
            component_type,
            count,
            max,
            min,
            type,
            None,
            export_settings,  # type: ignore
        )
    else:
        return base_gather_accessor(
            buffer_view,
            component_type,
            count,
            max,
            min,
            type,
            export_settings,  # type: ignore
        )
