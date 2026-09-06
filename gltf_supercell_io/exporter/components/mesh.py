from .component import glTF2BaseExporterComponent, requires_extension

import numpy as np
from typing import TYPE_CHECKING
from ...com import glTF_extension_name
from ...com.odin.constants import OdinAttributeType, OdinAttributeFormat
from ...com.odin.bounding_box import BoundingBox
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

        # Quick access map with joints indices for joints bound calculation
        self.skinned_streams: dict[
            int, dict[OdinAttributeType, OdinRawVertexAttribute]
        ] = {}

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

    def create_odin_stream_groups(
        self,
        primitive: "MeshPrimitive",
        primitives: list[tuple[OdinVertexAttribute, OdinRawVertexAttribute]],
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

            self.skinned_streams[id(primitive)] = {
                attribute.name: buffer for attribute, buffer in skinned_primitives
            }

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
        destination_format = OdinAttributeFormat(attribute.format)
        source_format = OdinAttributeFormat(buffer.source_format)
        destination_dtype = OdinAttributeFormat.to_numpy_dtype(destination_format)
        destination_count = OdinAttributeFormat.to_element_count(destination_format)

        def normalized_values(
            values: np.ndarray, fmt: OdinAttributeFormat
        ) -> np.ndarray:
            values = np.asarray(values)
            if OdinAttributeFormat.is_normalized(fmt) and np.issubdtype(
                values.dtype, np.integer
            ):
                return values.astype(np.float32) / np.iinfo(values.dtype).max
            return values

        def convert(values: np.ndarray) -> np.ndarray:
            # UInt bone weights use Odin's packed 11/11/10 representation.
            if (
                attribute.name == OdinAttributeType.a_boneweights
                and destination_format == OdinAttributeFormat.UInt
            ):
                values = normalized_values(np.asarray(values), source_format)
                values = np.asarray(values, dtype=np.float32).reshape(-1)
                values = np.pad(values, (0, max(0, 4 - values.size)))[:4]
                quantized = np.clip(
                    np.rint(values[1:4] / 0.0002442),
                    0,
                    [2047, 2047, 1023],
                ).astype(np.uint32)
                return np.asarray(
                    [(quantized[0] << 21) | (quantized[1] << 10) | quantized[2]],
                    dtype=np.uint32,
                )

            values = normalized_values(np.asarray(values), source_format)
            values = np.asarray(values).reshape(-1)
            if values.size > destination_count:
                values = values[:destination_count]
            elif values.size < destination_count:
                values = np.pad(values, (0, destination_count - values.size))

            if np.issubdtype(destination_dtype, np.integer):
                if OdinAttributeFormat.is_normalized(destination_format):
                    info = np.iinfo(destination_dtype)
                    values = np.rint(values * info.max)
                    values = np.clip(values, info.min, info.max)
                else:
                    info = np.iinfo(destination_dtype)
                    values = np.clip(values, info.min, info.max)
            return np.asarray(values, dtype=destination_dtype)

        for i in range(count):
            vertex = data[i]

            destination_vertex = vertex[attribute.name.name]
            source_vertex = buffer.data[i]
            if destination_format == source_format:
                destination_vertex[: len(source_vertex)] = source_vertex
                continue

            converted = convert(source_vertex)
            destination_vertex[: len(converted)] = converted

    def create_odin_buffer(
        self, attributes: list[tuple[OdinVertexAttribute, OdinRawVertexAttribute]]
    ):
        stride, layout = self.create_odin_layout(
            [attribute for attribute, _ in attributes]
        )
        vertex_count = min([buffer.data.shape[0] for _, buffer in attributes])
        data: np.ndarray[tuple[int], np.dtype[np.void]] = np.zeros(
            (vertex_count,), dtype=layout
        )
        for attribute, buffer in attributes:
            self.write_odin_buffer(vertex_count, attribute, buffer, data)

        offset = self.buffer_offset
        self.buffer_offset += data.nbytes
        self.buffers.append(data)

        return offset, stride

    def create_odin_primitive(self, primitive: "MeshPrimitive", mesh_bbox: BoundingBox):
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
            attribute_format = attribute.source_format
            match (id_type):
                case OdinAttributeType.a_boneweights:
                    # Normalize to UInt later
                    attribute_format = OdinAttributeFormat.UInt
                case OdinAttributeType.a_uv0 | OdinAttributeType.a_uv1:
                    # Normalize to short
                    attribute_format = OdinAttributeFormat.Short2Norm
                case OdinAttributeType.a_normal:
                    # Normalize byte
                    attribute_format = OdinAttributeFormat.Byte4Norm

            descriptor = OdinVertexAttribute(
                attribute_format, OdinAttributeType.to_index(id_type), id_type, 0
            )
            odin_attributes.append((descriptor, attribute))

            # Handle mesh bbox
            if id_type == OdinAttributeType.a_pos:
                bbox = BoundingBox()
                bbox.extend(attribute.data)
                mesh_bbox.union(bbox)

        groups = self.create_odin_stream_groups(primitive, odin_attributes)
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

    def gather_mesh_primitive(
        self,
        mesh: "Mesh",
        primitive: "MeshPrimitive",
        idx: int,
        mesh_bbox: BoundingBox,
        export_settings: dict,
    ):
        info = self.create_odin_primitive(primitive, mesh_bbox)
        if info is None:
            return

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
                f"{mesh.name} mesh primitive by index {idx} doesn't have proper odin material! Using generated fallback material..."
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

        primitive.extensions[glTF_extension_name] = Extension(
            glTF_extension_name, info_descriptor, True
        )

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

        bbox = BoundingBox()
        skinned_mask = 0
        for i, primitive in enumerate(gltf2_mesh.primitives):
            skinned_primitive = (
                OdinAttributeType.a_boneindex in primitive.attributes
                and OdinAttributeType.a_boneweights in primitive.attributes
            )

            if skinned_primitive:
                skinned_mask |= 1 << i

            self.gather_mesh_primitive(gltf2_mesh, primitive, i, bbox, export_settings)

        gltf2_mesh.name = None
        if gltf2_mesh.extensions is None:
            gltf2_mesh.extensions = {}

        mesh_extension = {
            "bounds": bbox.as_list(),
            "skinnedSubMeshMask": [
                skinned_mask & 0xFFFFFFFF,
                (skinned_mask >> 32) & 0xFFFFFFFF,
            ],
        }
        gltf2_mesh.extensions[glTF_extension_name] = Extension(
            glTF_extension_name, mesh_extension, True
        )

    @requires_extension
    def gather_skin_hook(
        self,
        gltf2_skin,
        blender_object,
        export_settings,
    ):
        if not self.properties.use_odin:
            return

        if gltf2_skin.extensions is None:
            gltf2_skin.extensions = {}

        # Prepare bounding box accessor for each joint
        gltf2_skin.extensions[glTF_extension_name] = Extension(
            glTF_extension_name,
            {"bounds": [BoundingBox() for _ in gltf2_skin.joints]},
            True,
        )

    @requires_extension
    def gather_node_hook(
        self,
        gltf2_node,
        blender_object,
        export_settings,
    ):
        if gltf2_node.mesh is None or gltf2_node.skin is None:
            return

        if not self.properties.use_odin:
            return

        # Calculating skin joints bound
        mesh = gltf2_node.mesh
        skin = gltf2_node.skin
        bounds = skin.extensions[glTF_extension_name].extension["bounds"]

        for primitive in mesh.primitives:
            attributes = self.skinned_streams.get(id(primitive))
            if attributes is None:
                continue

            vertices = attributes[OdinAttributeType.a_pos]
            indices = attributes[OdinAttributeType.a_boneindex]
            weights = attributes[OdinAttributeType.a_boneweights]

            vertex_count = min([buffer.data.shape[0] for buffer in attributes.values()])

            for i in range(len(skin.joints)):
                bound: BoundingBox = bounds[i]
                for vtx in range(vertex_count):
                    bone_indices: np.ndarray = indices.data[vtx]

                    joint_indices = np.where(bone_indices == i)
                    if len(joint_indices) == 0 or len(joint_indices[0]) == 0:
                        continue

                    joint_index = joint_indices[0][0]

                    vertex_weight = weights.data[vtx]
                    weight = vertex_weight[joint_index]
                    if 0.0 >= weight:
                        continue

                    vertex = vertices.data[vtx]
                    bound.union_point(vertex, vertex)

    @requires_extension
    def gather_gltf_extensions_hook(self, gltf, export_settings):
        if not self.properties.use_odin:
            return

        # Serialize bounds for skins
        for skin in gltf.skins or []:
            bounds: list[BoundingBox] = skin.extensions[glTF_extension_name]["bounds"]
            skin.extensions[glTF_extension_name]["bounds"] = [
                bound.as_flat_list() for bound in bounds
            ]
