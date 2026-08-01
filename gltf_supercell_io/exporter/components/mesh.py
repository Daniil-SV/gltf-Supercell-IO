from .component import glTF2BaseExporterComponent

import numpy as np
from typing import TYPE_CHECKING
from io_scene_gltf2.io.com.constants import ComponentType, DataType
from ...com.utilities.compatibility import array_to_accessor

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import Accessor, Mesh, MeshPrimitive


class MeshExporter(glTF2BaseExporterComponent):
    def convert_mesh_to_legacy(self, mesh: "Mesh", export_settings):
        # In older versions, joints were always saved in shorts, and this seems to be critical.
        # glTF exporter can apply optimizations to such things, so we need to ensure it's saved in the correct format here.
        target_type = ComponentType.UnsignedShort
        target_dtype = ComponentType.to_numpy_dtype(target_type)

        primitives: list["MeshPrimitive"] = mesh.primitives or []
        for primitive in primitives:
            accessors: dict[str, "Accessor"] = {
                name: value
                for name, value in primitive.attributes.items()
                if name.startswith("JOINTS_")
            }

            for name, accessor in accessors.items():
                if (
                    accessor.component_type != ComponentType.UnsignedByte
                    or accessor.type != DataType.Vec4
                ):
                    continue

                dtype = ComponentType.to_numpy_dtype(accessor.component_type)
                component_nb = DataType.num_elements(accessor.type)
                num_elems = accessor.count * component_nb
                array = np.frombuffer(
                    accessor.buffer_view.data,
                    dtype=np.dtype(dtype).newbyteorder("<"),
                    count=num_elems,
                ).reshape(accessor.count, 4)

                primitive.attributes[name] = array_to_accessor(
                    name,
                    array.astype(target_dtype),
                    export_settings,
                    target_type,
                    data_type=accessor.type,
                )

    def gather_mesh_hook(
        self,
        gltf2_mesh,
        blender_mesh,
        blender_object,
        vertex_groups,
        modifiers,
        materials,
        export_settings,
    ):
        if self.properties.legacy_meshes:
            self.convert_mesh_to_legacy(gltf2_mesh, export_settings)
