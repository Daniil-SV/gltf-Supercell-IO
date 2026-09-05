from .component import glTF2BaseExporterComponent, requires_extension

import numpy as np
from typing import TYPE_CHECKING
from ...com import glTF_extension_name
from ...com.odin.constants import OdinAttributeType, OdinAttributeFormat
from ...com.odin.attribute import (
    OdinRawVertexAttribute,
    OdinVertexAttribute,
    OdinVertexDescriptor,
    OdinMeshDataInfo,
)
from ...com.materials import ScShaderMaterial
from ...com.materials.variables import ShaderFloatVectorProperty
from io_scene_gltf2.io.com.constants import ComponentType, DataType
from io_scene_gltf2.blender.exp.accessors import array_to_accessor
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension, ChildOfRootExtension
from dataclasses import asdict

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import Accessor, Mesh, MeshPrimitive


SKINNING_STREAM = [
    OdinAttributeType.a_pos,
    OdinAttributeType.a_boneindex,
    OdinAttributeType.a_boneweights,
]


class MeshExporter(glTF2BaseExporterComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.buffer_offset = 0

    def create_odin_material_fallback(self):
        fallback = ScShaderMaterial()
        fallback.name = "lambert (generated)"
        fallback.add_constant("DIFFUSE")
        fallback.add_property(
            "diffuse", [0.7, 0.7, 0.7, 1.0], ShaderFloatVectorProperty
        )
        return fallback.to_typed_dict()

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

                legacy_joints = array_to_accessor(
                    name,
                    array.astype(target_dtype),
                    export_settings,
                    target_type,
                    data_type=accessor.type,
                )
                primitive.attributes[name] = legacy_joints

    def create_odin_descriptor_struct(
        self, primitives: dict[OdinAttributeType, OdinRawVertexAttribute]
    ):
        result = []

        for id_type, attribute in primitives.items():
            pass
            # result.append(
            #     (id_type.name, OdinAttributeType.)
            # )

    def create_odin_stream_groups(
        self, primitives: list[tuple[OdinVertexAttribute, OdinRawVertexAttribute]]
    ) -> list[list[tuple[OdinVertexAttribute, OdinRawVertexAttribute]]]:
        added_attributes: set[OdinAttributeType] = set()
        groups = []
        has_skin = False
        for desc, _ in primitives:
            if (
                desc.name == OdinAttributeType.a_boneweights
                or desc.name == OdinAttributeType.a_boneindex
            ):
                has_skin = True
                break

        # Create skinned stream
        if has_skin:
            skinned_primitives = [
                (desc, attribute)
                for desc, attribute in primitives
                if desc.name in SKINNING_STREAM
            ]

            if len(skinned_primitives) != 0:
                groups.append(skinned_primitives)
                added_attributes.update(SKINNING_STREAM)

        # Create stream with rest of attributes
        attributes = [
            (desc, attribute)
            for desc, attribute in primitives
            if desc.name not in added_attributes
        ]

        if len(attributes) != 0:
            groups.append(attributes)

        return groups

    @staticmethod
    def get_odin_format(data: OdinRawVertexAttribute):
        if data.data_type == "SCALAR":
            match (data.component_type):
                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt
                case ComponentType.Float:
                    return OdinAttributeFormat.Float

        if data.data_type == "VEC2":
            match (data.component_type):
                case ComponentType.Byte:
                    return OdinAttributeFormat.Byte2
                case ComponentType.UnsignedByte:
                    return OdinAttributeFormat.UByte2

                case ComponentType.Short:
                    return OdinAttributeFormat.Short2
                case ComponentType.UnsignedShort:
                    return OdinAttributeFormat.UShort2

                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt2
                case ComponentType.Float:
                    return OdinAttributeFormat.Float2

        if data.data_type == "VEC3":
            match (data.component_type):
                case ComponentType.Byte:
                    return OdinAttributeFormat.Byte3
                case ComponentType.UnsignedByte:
                    return OdinAttributeFormat.UByte3

                case ComponentType.Short:
                    return OdinAttributeFormat.Short3
                case ComponentType.UnsignedShort:
                    return OdinAttributeFormat.UShort3

                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt3
                case ComponentType.Float:
                    return OdinAttributeFormat.Float3

        if data.data_type == "VEC4":
            match (data.component_type):
                case ComponentType.Byte:
                    return OdinAttributeFormat.Byte4
                case ComponentType.UnsignedByte:
                    return OdinAttributeFormat.UByte4

                case ComponentType.Short:
                    return OdinAttributeFormat.Short4
                case ComponentType.UnsignedShort:
                    return OdinAttributeFormat.UShort4

                case ComponentType.UnsignedInt:
                    return OdinAttributeFormat.UInt4
                case ComponentType.Float:
                    return OdinAttributeFormat.Float4

        if data.data_type == "MAT2" and data.component_type == ComponentType.Float:
            return OdinAttributeFormat.Float3x3

        if data.data_type == "MAT3" and data.component_type == ComponentType.Float:
            return OdinAttributeFormat.Float2x2

        if data.data_type == "MAT4" and data.component_type == ComponentType.Float:
            return OdinAttributeFormat.Float4x4

        raise Exception("Unsupported odin mesh format")

    def create_odin_layout(self, attributes: list[OdinVertexAttribute]):
        offset = 0
        layout = []

        for attribute in attributes:
            name = attribute.name.name
            dtype = OdinAttributeFormat.to_numpy_dtype(attribute.format)
            count = OdinAttributeFormat.to_element_count(attribute.format)
            layout.append((name, dtype, (count,)))
            attribute.offset = offset
            offset += dtype.itemsize * count

        return offset, np.dtype(layout)

    def write_odin_buffer(
        self,
        count: int,
        attribute: OdinVertexAttribute,
        buffer: OdinRawVertexAttribute,
        data: np.ndarray,
    ):
        for i in range(count):
            vertex = data[i]

            destination_vertex = vertex[attribute.name.name]
            source_vertex = buffer.data[i]

            destination_vertex[: len(source_vertex)] = source_vertex

    def create_odin_buffer(
        self, attributes: list[tuple[OdinVertexAttribute, OdinRawVertexAttribute]]
    ):
        stride, layout = self.create_odin_layout(
            [attribute for attribute, _ in attributes]
        )
        vertex_count = min([buffer.data.shape[0] for _, buffer in attributes])
        data = np.zeros((vertex_count,), dtype=layout)
        for attribute, buffer in attributes:
            self.write_odin_buffer(vertex_count, attribute, buffer, data)

        offset = self.buffer_offset
        self.buffer_offset += data.nbytes
        self.buffers.append(data)
        return offset, stride

    def create_odin_primitive(self, primitive: "MeshPrimitive"):
        info = OdinMeshDataInfo()
        attribute_mapping: dict[OdinAttributeType, OdinRawVertexAttribute] = {}

        attributes = primitive.attributes.copy().items()
        for id_type, attribute in attributes:
            if not isinstance(id_type, OdinAttributeType) and not isinstance(
                attribute, OdinRawVertexAttribute
            ):
                continue

            attribute_mapping[id_type] = attribute
            del primitive.attributes[id_type]

        odin_attributes: list[tuple[OdinVertexAttribute, OdinRawVertexAttribute]] = []
        for i, (id_type, attribute) in enumerate(attribute_mapping.items()):
            attribute_format = MeshExporter.get_odin_format(attribute)
            descriptor = OdinVertexAttribute(attribute_format, i, id_type, 0)
            odin_attributes.append((descriptor, attribute))

        groups = self.create_odin_stream_groups(odin_attributes)
        if len(groups) == 0:
            return None

        for group in groups:
            offset, stride = self.create_odin_buffer(group)
            info.vertexDescriptors.append(
                OdinVertexDescriptor(
                    [attribute for attribute, _ in group], offset, stride
                )
            )

        return info

    @requires_extension
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
            return

        if len(gltf2_mesh.primitives) == 0:
            return

        for i, primitive in enumerate(gltf2_mesh.primitives):
            info = self.create_odin_primitive(primitive)
            if info is None:
                continue

            # Handling material reference
            material_data: dict | None = None
            if primitive.material is not None:
                material = primitive.material
                if (
                    material.extensions is not None
                    and glTF_extension_name in material.extensions
                ):
                    # Pick up converted material in material hook
                    material_data = material.extensions[glTF_extension_name]

            # Odin primitive is mandatory to have material
            if primitive.material is None or material_data is None:
                material_data = self.create_odin_material_fallback()
                export_settings["log"].warning(
                    f"{gltf2_mesh.name} mesh primitive by index {i} doesn't have proper odin material! Using generated fallback material..."
                )

            primitive.material = ChildOfRootExtension(
                ["materials"], glTF_extension_name, material_data, True
            )

            # Handling mesh reference
            root_extension = ChildOfRootExtension(
                ["meshDataInfos"], glTF_extension_name, asdict(info), True
            )

            info_descriptor = {"meshDataInfoIndex": root_extension}
            if primitive.extensions is None:
                primitive.extensions = {}

            gltf2_mesh.name = None
            primitive.extensions[glTF_extension_name] = Extension(
                glTF_extension_name, info_descriptor, True
            )
