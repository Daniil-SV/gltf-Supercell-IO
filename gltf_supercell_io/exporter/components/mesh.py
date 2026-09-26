from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from io_scene_gltf2.blender.exp.accessors import array_to_accessor
from io_scene_gltf2.io.com.constants import ComponentType, DataType
from io_scene_gltf2.io.com.gltf2_io import Accessor
from io_scene_gltf2.io.com.gltf2_io_extensions import ChildOfRootExtension, Extension

from ...com import glTF_extension_name
from ...com.materials import ScShaderMaterial
from ...com.materials.variables import ShaderFloatVectorProperty
from ...com.odin.attribute import (
    OdinMeshDataInfo,
    OdinRawVertexAttribute,
    OdinVertexAttribute,
    OdinVertexDescriptor,
)
from ...com.odin.bounding_box import BoundingBox
from ...com.odin.constants import OdinAttributeFormat, OdinAttributeType
from .component import glTF2BaseExporterComponent, requires_extension, requires_odin

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import Mesh, MeshPrimitive


SKINNING_STREAM = [
    OdinAttributeType.a_pos,
    OdinAttributeType.a_boneindex,
    OdinAttributeType.a_boneweights,
]


@dataclass
class OdinVertexPool:
    info: OdinMeshDataInfo
    signature: tuple
    skinned: bool
    chunks: list[list[np.ndarray]]
    vertex_ids: dict[bytes, int] = field(default_factory=dict)
    vertex_count: int = 0
    root_extension: ChildOfRootExtension | None = None


class MeshExporter(glTF2BaseExporterComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.pool: list[OdinVertexPool] = []
        self.pool_cache: dict[int, OdinVertexPool] = {}
        self.bbox: dict[int, BoundingBox] = {}
        self.joints_bbox: dict[int, dict[int, BoundingBox]] = {}

    def gather_odin_indices(self, indices: np.ndarray, export_settings: dict):
        """Place one primitive's indices in Odin's shared buffer view."""
        max_index = indices.max()

        component_type = ComponentType.UnsignedInt
        if max_index < 65535:
            component_type = ComponentType.UnsignedShort
        elif max_index < 4294967295:
            component_type = ComponentType.UnsignedInt
        else:
            export_settings["log"].error(
                "Primitive has too many vertices for Odin indices"
            )

        index_data = indices.astype(
            ComponentType.to_numpy_dtype(component_type), copy=False
        )

        index_offset = len(self.index_buffer)
        self.index_buffer += index_data.tobytes()

        return Accessor(
            buffer_view=self.odin_view,
            byte_offset=index_offset,
            component_type=component_type,
            count=len(index_data),
            extensions=None,
            extras=None,
            max=None,
            min=None,
            name=None,
            normalized=None,
            sparse=None,
            type=DataType.Scalar,
        )

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

        primitives: list[MeshPrimitive] = mesh.primitives or []
        for primitive in primitives:
            accessors: dict[str, Accessor] = {
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

    def write_odin_buffer(
        self,
        count: int,
        attribute: OdinVertexAttribute,
        buffer: OdinRawVertexAttribute,
        output: np.ndarray,
        bbox: BoundingBox | None = None,
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
            vertex = output[i]

            destination_vertex = vertex[attribute.name.name]
            source_vertex = buffer.data[i]
            if bbox is not None:
                bbox.union_point(source_vertex, source_vertex)

            if destination_format == source_format:
                destination_vertex[: len(source_vertex)] = source_vertex
                continue

            converted = convert(source_vertex)

            destination_vertex[: len(converted)] = converted

    def create_odin_vertex_groups(
        self,
        attributes: list[OdinAttributeType],
    ) -> list[list[OdinAttributeType]]:
        added_attributes: set[OdinAttributeType] = set()
        groups = []
        has_skin = False
        for attribute in attributes:
            if (
                attribute == OdinAttributeType.a_boneweights
                or attribute == OdinAttributeType.a_boneindex
            ):
                has_skin = True
                break

        # Create skinned group
        if has_skin:
            skinned_primitives = [
                attribute for attribute in attributes if attribute in SKINNING_STREAM
            ]

            if len(skinned_primitives) != 0:
                groups.append(skinned_primitives)
                added_attributes.update(SKINNING_STREAM)

        # Create group with rest of attributes
        attributes = [
            attribute for attribute in attributes if attribute not in added_attributes
        ]

        if len(attributes) != 0:
            groups.append(attributes)

        return groups

    def create_odin_layout(self, attributes: list[OdinVertexAttribute]):
        stride = 0
        layout = []

        for attribute in attributes:
            name = attribute.name.name
            dtype = OdinAttributeFormat.to_numpy_dtype(attribute.format)
            count = OdinAttributeFormat.to_element_count(attribute.format)
            layout.append((name, dtype, (count,)))
            attribute.offset = stride
            stride += dtype.itemsize * count

        return stride, layout

    def create_odin_descriptor(
        self, attributes: dict[OdinAttributeType, OdinRawVertexAttribute]
    ):
        info = OdinMeshDataInfo()

        vertex_attributes: dict[OdinAttributeType, OdinVertexAttribute] = {}
        for id_type, attribute in attributes.items():
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

            vertex_attribute = OdinVertexAttribute(
                attribute_format, OdinAttributeType.to_index(id_type), id_type, 0
            )
            vertex_attributes[id_type] = vertex_attribute

        groups = self.create_odin_vertex_groups([attribute for attribute in attributes])

        if len(groups) == 0:
            return info

        for group in groups:
            info.vertexDescriptors.append(
                OdinVertexDescriptor(
                    [vertex_attributes[attribute] for attribute in group], 0, 0
                )
            )

        return info

    def create_odin_joints_bbox(
        self,
        position: np.ndarray,
        indices: np.ndarray,
        weights: np.ndarray,
        joints_bbox: dict[int, BoundingBox],
    ):
        vertex_count = min([buffer.shape[0] for buffer in [position, indices, weights]])

        for vtx in range(vertex_count):
            vertex_position = position[vtx]
            vertex_indices = indices[vtx]
            vertex_weights = weights[vtx]

            influence_count = min(
                [buffer.shape[0] for buffer in [vertex_indices, vertex_weights]]
            )
            for itx in range(influence_count):
                bone_weight = vertex_weights[itx]
                if 0.0 >= bone_weight:
                    continue

                bone_index = vertex_indices[itx]
                bbox = joints_bbox.setdefault(int(bone_index), BoundingBox())
                bbox.union_point(vertex_position, vertex_position)

    def gather_odin_vertices(
        self,
        attributes: dict[OdinAttributeType, OdinRawVertexAttribute],
        bbox: BoundingBox,
        joints_bbox: dict[int, BoundingBox],
    ) -> tuple[OdinVertexPool, list[np.ndarray]]:
        """Pack one primitive and select the latest compatible stream pool."""
        info = self.create_odin_descriptor(attributes)
        vertex_count = next(iter(attributes.values())).data.shape[0]
        if any(
            attribute.data.shape[0] != vertex_count for attribute in attributes.values()
        ):
            raise ValueError(
                "Odin primitive attributes have inconsistent vertex counts"
            )

        chunks: list[np.ndarray] = []
        signature = []
        attribute_types = [attribute for attribute in attributes]
        skinned = (
            OdinAttributeType.a_boneindex in attribute_types
            and OdinAttributeType.a_boneweights in attribute_types
        )

        # Calculating bones bbox
        if skinned:
            position = attributes[OdinAttributeType.a_pos]
            bone_index = attributes[OdinAttributeType.a_boneindex]
            bone_weights = attributes[OdinAttributeType.a_boneweights]
            self.create_odin_joints_bbox(
                position.data, bone_index.data, bone_weights.data, joints_bbox
            )

        for descriptor in info.vertexDescriptors:
            stride, layout = self.create_odin_layout(descriptor.attributes)
            descriptor.stride = stride

            chunk = np.zeros(vertex_count, dtype=np.dtype(layout))
            for attribute in descriptor.attributes:
                self.write_odin_buffer(
                    vertex_count,
                    attribute,
                    attributes[attribute.name],
                    chunk,
                    bbox if attribute.name == OdinAttributeType.a_pos else None,
                )

            chunks.append(chunk)
            signature.append(
                (
                    stride,
                    tuple(
                        (attribute.name, attribute.format, attribute.offset)
                        for attribute in descriptor.attributes
                    ),
                )
            )

        signature = tuple(signature)
        if self.pool and self.pool[-1].signature == signature:
            return self.pool[-1], chunks

        pool = OdinVertexPool(
            info=info,
            signature=signature,
            skinned=skinned,
            chunks=[[] for _ in chunks],
        )

        pool.root_extension = ChildOfRootExtension(
            ["meshDataInfos"], glTF_extension_name, info, True
        )
        self.pool.append(pool)
        return pool, chunks

    def finalize_odin_vertices(self):
        buffer_offset = len(self.index_buffer)

        for pool in self.pool:
            for descriptor, chunks in zip(
                pool.info.vertexDescriptors,
                pool.chunks,
            ):
                # Align descriptor start to 4 bytes
                padding = (-buffer_offset) % 4
                if padding:
                    self.vertex_buffer += b"\x00" * padding
                    buffer_offset += padding

                data = np.concatenate(chunks) if chunks else np.empty(0)

                descriptor.offset = buffer_offset
                buffer_offset += data.nbytes
                self.vertex_buffer += data.tobytes()

    def gather_odin_material(
        self,
        mesh: "Mesh",
        primitive: "MeshPrimitive",
        idx: int,
        export_settings: dict,
    ):
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

    def gather_odin_mesh(self, mesh: "Mesh", export_settings: dict):
        primitives: list[MeshPrimitive] = mesh.primitives or []

        skinned_mask = 0
        bbox = BoundingBox()
        has_static = False
        for i, primitive in enumerate(primitives):
            self.gather_odin_material(mesh, primitive, i, export_settings)

            key: int = id(primitive.attributes)
            pool = self.pool_cache.get(key)
            if pool is None:
                continue

            if pool.skinned:
                skinned_mask |= 1 << i
            else:
                has_static = True

            primitive_bbox = self.bbox.get(key)
            if primitive_bbox and not primitive_bbox.empty:
                bbox.union(primitive_bbox)

            if primitive.extensions is None:
                primitive.extensions = {}

            info_descriptor = {"meshDataInfoIndex": pool.root_extension}
            if primitive.extensions is None:
                primitive.extensions = {}

            primitive.extensions[glTF_extension_name] = Extension(
                glTF_extension_name, info_descriptor, True
            )

        mesh_extension = {
            "bounds": bbox.as_list(),
            "skinnedSubMeshMask": [
                skinned_mask & 0xFFFFFFFF,
                (skinned_mask >> 32) & 0xFFFFFFFF,
            ],
        }

        if has_static:
            mesh_extension["isPretransformed"] = True

        mesh.extensions[glTF_extension_name] = Extension(
            glTF_extension_name, mesh_extension, True
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
        if len(gltf2_mesh.primitives) == 0:
            return

        if self.properties.legacy_meshes:
            self.convert_mesh_to_legacy(gltf2_mesh, export_settings)
            return

        if self.properties.use_odin:
            self.gather_odin_mesh(gltf2_mesh, export_settings)
            gltf2_mesh.name = None

    @requires_odin
    def gather_skin_hook(
        self,
        gltf2_skin,
        blender_object,
        export_settings,
    ):
        if gltf2_skin.extensions is None:
            gltf2_skin.extensions = {}

        # Allocate bounding boxes for each joint
        gltf2_skin.extensions[glTF_extension_name] = Extension(
            glTF_extension_name,
            {"bounds": [BoundingBox() for _ in gltf2_skin.joints]},
            True,
        )

    @requires_odin
    def gather_node_hook(
        self,
        gltf2_node,
        blender_object,
        export_settings,
    ):
        """
        We need a moment when both the skin and the mesh are completely ready to begin calculating bounding box
        This hook provides a node that (may) contains a reference to both the mesh and the skin,
        which means the conditions we need so we can calculate the bounding box for the current mesh and its skin
        """

        mesh = gltf2_node.mesh
        skin = gltf2_node.skin

        # Filter non skinned or non mesh nodes
        if mesh is None or skin is None:
            return

        bounds: list[BoundingBox] = skin.extensions[glTF_extension_name].extension[
            "bounds"
        ]

        # Combining all primitive bounding boxes to skin
        for primitive in mesh.primitives:
            primitive_bounds = self.joints_bbox.get(id(primitive.attributes))
            if primitive_bounds is None:
                continue

            for i in range(len(skin.joints)):
                if i not in primitive_bounds:
                    continue

                target_bbox = bounds[i]
                target_bbox.union(primitive_bounds[i])

    @requires_odin
    def gather_gltf_extensions_hook(self, gltf, export_settings):
        gltf.scene = None
        gltf.scenes = None

    @requires_odin
    def gather_primitive_hook(self, primitive, export_settings):
        """
        Custom hook which provides full access for primitive attributes data
        Used to convert indices and attributes data to odin
        """
        if primitive.attributes is None or len(primitive.attributes) == 0:
            return

        # Gathering all odin attributes
        odin_attributes: dict[OdinAttributeType, OdinRawVertexAttribute] = {}

        attributes = primitive.attributes.copy().items()
        for id_type, attribute in attributes:
            if not isinstance(id_type, OdinAttributeType) or not isinstance(
                attribute, OdinRawVertexAttribute
            ):
                continue

            odin_attributes[id_type] = attribute

            # Remove odin attribute proxy
            del primitive.attributes[id_type]

        if not odin_attributes:
            export_settings["log"].warning(
                "Mesh primitive doesn't have any compatible odin attribute. Skip..."
            )
            return

        if OdinAttributeType.a_pos not in odin_attributes:
            export_settings["log"].warning(
                "Mesh primitive doesn't have vertex attribute. Skip..."
            )
            return

        bbox = BoundingBox()
        joints_bbox = {}
        pool, streams = self.gather_odin_vertices(odin_attributes, bbox, joints_bbox)
        vertex_count = streams[0].shape[0]
        if any(stream.shape[0] != vertex_count for stream in streams):
            raise ValueError(
                "Odin primitive attributes have inconsistent vertex counts"
            )

        if primitive.indices is None:
            source_indices = np.arange(vertex_count, dtype=np.int64)
        else:
            source_indices = np.asarray(primitive.indices, dtype=np.int64)
            if source_indices.size and (
                source_indices.min() < 0 or source_indices.max() >= vertex_count
            ):
                raise ValueError("Primitive index lies outside its Odin vertex pool")

        source_to_pool = np.empty(vertex_count, dtype=np.uint32)
        new_sources: list[int] = []
        for source_index in range(vertex_count):
            key = b"".join(stream[source_index].tobytes() for stream in streams)
            pool_index = pool.vertex_ids.get(key)
            if pool_index is None:
                pool_index = pool.vertex_count
                pool.vertex_ids[key] = pool_index
                pool.vertex_count += 1
                new_sources.append(source_index)
            source_to_pool[source_index] = pool_index

        if new_sources:
            source = np.asarray(new_sources, dtype=np.intp)
            for chunks, stream in zip(pool.chunks, streams):
                chunks.append(stream[source].copy())

        primitive.indices = source_to_pool[source_indices]
        primitive.indices = self.gather_odin_indices(primitive.indices, export_settings)

        key = id(primitive.attributes)
        self.bbox[key] = bbox
        self.pool_cache[key] = pool
        self.joints_bbox[key] = joints_bbox

    @requires_odin
    def gather_gltf_hook(self, active_scene_idx, scenes, animations, export_settings):
        # Flush vertex pool to single vertex buffer blob
        self.finalize_odin_vertices()
