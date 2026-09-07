import bpy
import numpy as np
from ...com.utilities.patcher import Patch
from io_scene_gltf2.io.com.constants import ComponentType, DataType, BufferViewTarget
from io_scene_gltf2.blender.exp.cache import cached_by_key
from io_scene_gltf2.blender.exp.primitives import (
    get_primitive_cache_key,
    __gather_targets,
    __gather_cache_primitives as base_primitive_cache,
    __gather_attributes,
)
from io_scene_gltf2.io.exp.binary_data import BinaryData
import io_scene_gltf2.blender.exp.pointcloud as pointcloud
from io_scene_gltf2.blender.exp.primitive_extract import extract_primitives
from io_scene_gltf2.blender.exp.accessors import gather_accessor
from io_scene_gltf2.io.exp.user_extensions import export_user_extensions
from typing import TYPE_CHECKING, Optional
from ..components.component import PrimitiveData

if TYPE_CHECKING:
    from ..ui import glTFSupercellExporterProperties


@cached_by_key(key=get_primitive_cache_key)
def __gather_cache_primitives(
    materials: tuple[bpy.types.Material],
    blender_data,
    uuid_for_skined_data,
    vertex_groups: bpy.types.VertexGroups,
    modifiers: Optional[bpy.types.ObjectModifiers],
    export_settings,
):
    """
    Gather parts that are identical for instances, i.e. excluding materials.
    """
    props: "glTFSupercellExporterProperties" = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore
    if not props.use_odin:
        return base_primitive_cache(
            materials,
            blender_data,
            uuid_for_skined_data,
            vertex_groups,
            modifiers,
            export_settings,
        )

    if type(blender_data).__name__ == "PointCloud":
        blender_primitives = pointcloud.gather_point_cloud(
            blender_data,
            export_settings,
        )
        additional_materials_udim = [None] * len(blender_primitives)
        shared_attributes = None

    else:
        (
            blender_primitives,
            additional_materials_udim,
            shared_attributes,
        ) = extract_primitives(
            materials,
            blender_data,
            uuid_for_skined_data,
            vertex_groups,
            modifiers,
            export_settings,
        )

    common_attributes = {}
    common_targets = []
    if shared_attributes is not None:
        shared_primitive = {
            "attributes": shared_attributes,
        }

        common_attributes = __gather_attributes(
            shared_primitive,
            blender_data,
            modifiers,
            export_settings,
        )
        common_targets = __gather_targets(
            shared_primitive,
            blender_data,
            modifiers,
            export_settings,
        )

    primitives = []
    for internal_primitive in blender_primitives:
        mode: str = internal_primitive.get("mode")

        if mode is None and shared_attributes is not None:
            attributes = common_attributes
            targets = common_targets
        else:
            attributes = __gather_attributes(
                internal_primitive,
                blender_data,
                modifiers,
                export_settings,
            )
            targets = __gather_targets(
                internal_primitive,
                blender_data,
                modifiers,
                export_settings,
            )

        material = internal_primitive.get("material")
        indices = internal_primitive.get("indices")
        primitive = PrimitiveData(
            attributes,
            indices,
            mode,  # type: ignore
            None if material is None else materials[material],
            targets,
        )
        export_user_extensions("gather_primitive_hook", export_settings, primitive)

        if isinstance(primitive.indices, np.ndarray):
            # NOTE: Values used by some graphics APIs as "primitive restart" values are disallowed.
            # Specifically, the values 65535 (in UINT16) and 4294967295 (in UINT32) cannot be used as indices.
            # https://github.com/KhronosGroup/glTF/issues/1142
            # https://github.com/KhronosGroup/glTF/pull/1476/files
            # Also, UINT8 mode is not supported:
            # https://github.com/KhronosGroup/glTF/issues/1471
            max_index = primitive.indices.max()
            if max_index < 65535:
                indices_type = ComponentType.UnsignedShort
                primitive.indices = primitive.indices.astype(np.uint16, copy=False)
            elif max_index < 4294967295:
                indices_type = ComponentType.UnsignedInt
                primitive.indices = primitive.indices.astype(np.uint32, copy=False)
            else:
                export_settings["log"].error(
                    "A mesh contains too many vertices ("
                    + str(max_index)
                    + ") and needs to be split before export."
                )

            indices_data = BinaryData(
                primitive.indices.tobytes(),
                bufferViewTarget=BufferViewTarget.ELEMENT_ARRAY_BUFFER,
            )

            primitive.indices = gather_accessor(
                indices_data,
                indices_type,  # type: ignore
                len(primitive.indices),
                None,
                None,
                DataType.Scalar,  # type: ignore
                None,
                export_settings,
            )

        primitives.append(
            {
                "attributes": primitive.attributes,
                "indices": primitive.indices,
                "mode": primitive.mode,
                "material": material,
                "targets": primitive.targets,
                "uvmap_attributes_index": internal_primitive.get(
                    "uvmap_attributes_index"
                ),
            }
        )

    return primitives, additional_materials_udim


# Explanation: Conversion to Odin mesh involves almost the entire primitive path: indices, attributes, etc
# io_scene_gltf2 doesn't provide enough hooks to make Odin conversion as efficient as possible
# The only way is to re-encode attributes and indices, which can take an inordinate amount of time
# So this hook is designed to optimize these processes specifically for odin export pipeline
# and add additional plugin hooks in the necessary places
# Of course, this area is incredibly sensitive to API changes and will likely require
# a lot of maintenance with each version, but it's worth
# it given how much it improves the user experience
primitive_master_hook = Patch(
    "custom primitive hook",
    module_path="io_scene_gltf2.blender.exp.primitives",
    target_method="__gather_cache_primitives",
    function=__gather_cache_primitives,
)
