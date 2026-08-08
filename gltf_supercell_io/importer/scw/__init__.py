from ...com.utilities.binary_reader import BinaryReader, Endian
from ...com.utilities.accessor import MemoryAccessor
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.imp.gltf2_io_gltf import ImportError
from .chunks import ScwChunk
from .chunks.header import ScwHeader
from .chunks.geometry import ScwGeometry, ScwWeights
from .chunks.nodes import ScwNodes
from .chunks.material import ScwMaterial, Color as ScwColor, Texture as ScwTexture
from .chunks.instance.controller_instance import (
    ScwGeometryInstance,
    ScwControllerInstance,
)
from .chunks.sub.attribute import ScwAttribute
from .chunks.sub.primitive import ScwPrimitive
from .chunks.sub.joint import ScwJoint
from os.path import isfile
from typing import Optional, cast
from io_scene_gltf2.io.com.gltf2_io import (
    Gltf,
    Node,
    Mesh,
    MeshPrimitive,
    Material,
    Skin,
)
from ...com import glTF_material_extension_name
from copy import copy
from dataclasses import dataclass
import numpy as np

CHUNKS: list[type[ScwChunk]] = [ScwHeader]


@dataclass(frozen=True)
class CachedMeshInstance:
    name: str
    bindings: tuple[tuple[str, str], ...]


def _source_to_gltf_name(name: str):
    match name.casefold():
        case "position" | "vertex":
            return "POSITION"
        case "normal":
            return "NORMAL"
        case "texcoord":
            return "TEXCOORD_0"
        case _:
            raise ImportError(f"Unknown SCW attribute name {name}")


class ScwFile:
    def __init__(self, filename: str, settings: dict) -> None:
        self.filename = filename
        self.gltf = glTFImporter(filename, settings)
        self.imported_meshes: dict[str, Mesh] = {}
        self.imported_materials: list[str] = []
        self.imported_skins: dict[str, tuple[ScwJoint, ...]] = {}
        self.mesh_instances: dict[CachedMeshInstance, int] = {}
        self.version = -1

    def _import_header(self, header: ScwHeader):
        self.version = header.version

    def _create_accessor(self, arr: np.ndarray) -> int:
        result = len(self.gltf.data.accessors)

        self.gltf.data.accessors.append(MemoryAccessor(arr))
        return result

    def _import_primitive(
        self,
        primitive: ScwPrimitive,
        sources: tuple[ScwAttribute, ...],
        weights: Optional[ScwWeights] = None,
    ):
        indices: tuple[tuple[ScwAttribute, np.ndarray], ...] = tuple(
            [
                (source, primitive.attribute_indices[source.triangles_index])
                for source in sources
            ]
        )

        vertex_keys = np.stack(
            [attribute_indices.reshape(-1) for _, attribute_indices in indices],
            axis=1,
        )

        unique_keys, unique_indices, inverse = np.unique(
            vertex_keys,
            axis=0,
            return_index=True,
            return_inverse=True,
        )

        order = np.argsort(unique_indices)

        remap = np.empty_like(order)
        remap[order] = np.arange(len(order))

        gltf_indices = remap[inverse].astype(np.uint32, copy=False)

        attributes: dict[str, int] = {}
        for attribute_index, (source, _) in enumerate(indices):
            source_indices = unique_keys[order, attribute_index]
            data = source.data[source_indices]

            attribute_name = _source_to_gltf_name(source.name)
            attributes[attribute_name] = self._create_accessor(data)

        if weights is not None:
            position_index = next(
                i
                for i, (source, _) in enumerate(indices)
                if source.name in ["POSITION", "VERTEX"]
            )

            position_indices = unique_keys[
                order,
                position_index,
            ]

            joints = weights.joints[position_indices]
            weight_values = weights.weights[position_indices]

            attributes["JOINTS_0"] = self._create_accessor(joints)
            attributes["WEIGHTS_0"] = self._create_accessor(weight_values)

        indices_accessor = self._create_accessor(gltf_indices)
        return (indices_accessor, attributes)

    def _import_mesh(self, mesh: ScwGeometry):
        gltf_primitives: list[MeshPrimitive] = []
        for primitive in mesh.primitives:
            indices, attributes = self._import_primitive(
                primitive, mesh.attributes, mesh.weights
            )

            gltf_primitives.append(
                MeshPrimitive(
                    attributes=attributes,
                    extensions=None,
                    extras=None,
                    indices=indices,
                    material=primitive.material_bind_name,
                    mode=4,
                    targets=None,
                )
            )

        if len(mesh.joints) > 0:
            joints = mesh.joints
            if mesh.bind_matrix is not None:
                for joint in joints:
                    joint.inverse_bind_matrix = (
                        mesh.bind_matrix @ joint.inverse_bind_matrix
                    )

            self.imported_skins[mesh.name] = joints

        self.imported_meshes[mesh.name] = Mesh(
            extensions=None,
            extras=None,
            name=mesh.name,
            primitives=gltf_primitives,
            weights=None,
        )

    def _instantiate_mesh(self, name: str, bindings: dict[str, str]):
        # Cache all instantiate calls to same mesh with same material bindings
        key = CachedMeshInstance(
            name, tuple([(key, value) for key, value in bindings.items()])
        )
        cached = self.mesh_instances.get(key)
        if cached is not None:
            return cached

        mesh_idx = len(self.gltf.data.meshes)
        mesh = copy(self.imported_meshes[name])
        mesh.primitives = [copy(primitive) for primitive in mesh.primitives]
        for primitive in mesh.primitives:
            source_material: str = primitive.material

            # Should not happen, skip just in case
            if source_material not in bindings:
                continue

            target_material = bindings[source_material]

            # Probably material is defined in materials file
            # Create fallback material so we could override it from material file later
            if target_material not in self.imported_materials:
                self._create_fallback_material(target_material)

            primitive.material = list(self.imported_materials).index(target_material)

        self.gltf.data.meshes.append(mesh)
        self.mesh_instances[key] = mesh_idx
        return mesh_idx

    def _instantiate_mesh_instance(self, instance: ScwGeometryInstance) -> int:
        return self._instantiate_mesh(instance.target_mesh, instance.material_binding)

    def _create_skin(self, name: str, nodes: ScwNodes) -> int:
        joints_idx: list[int] = []
        inv_matrices: int | None = None

        if name in self.imported_skins:
            keys = [node.name for node in nodes.nodes]
            joints = self.imported_skins[name]

            joints_idx = [keys.index(joint.name) for joint in joints]
            joints_matrices = [joint.inverse_bind_matrix for joint in joints]
            inv_matrices = self._create_accessor(
                np.asarray(
                    [matrix[:] for matrix in joints_matrices], dtype=np.float32
                ).reshape(-1, 16)
            )

        skin_idx = len(self.gltf.data.skins)
        gltf_skin = Skin(
            name=None,
            extensions=None,
            extras=None,
            inverse_bind_matrices=inv_matrices,
            joints=joints_idx,
            skeleton=None,
        )
        self.gltf.data.skins.append(gltf_skin)
        return skin_idx

    def _instantiate_skinned_mesh_instance(
        self, instance: ScwControllerInstance, nodes: ScwNodes
    ) -> tuple[int, int]:
        mesh_idx = self._instantiate_mesh(
            instance.target_mesh, instance.material_binding
        )

        skin_idx = self._create_skin(instance.target_mesh, nodes)
        return (mesh_idx, skin_idx)

    def _import_nodes(self, nodes: ScwNodes):
        gltf_nodes = [
            Node(
                camera=None,
                children=[],
                extensions=None,
                extras=None,
                matrix=None,
                mesh=None,
                name=node.name,
                rotation=None,
                scale=None,
                translation=None,
                weights=None,
                skin=None,
            )
            for node in nodes.nodes
        ]

        def gather_children(name: str):
            result: list[int] = []
            for i, node in enumerate(nodes.nodes):
                if node.parent == name:
                    result.append(i)

            return result

        for idx in range(len(nodes.nodes)):
            gltf_node = gltf_nodes[idx]
            node = nodes.nodes[idx]

            # Converting parent-based tree to child-based tree
            gltf_node.children = gather_children(cast(str, node.name))

            # Processing node bind transformation
            if len(node.frames) > 0:
                frame = node.frames[0]
                gltf_node.translation = [val or 0.0 for val in frame.translation.values]  # type: ignore
                if frame.rotation is not None:
                    gltf_node.rotation = list(frame.rotation)  # type: ignore

                gltf_node.scale = [val or 1.0 for val in frame.scale.values]  # type: ignore

            # Processing instances
            for instance in node.instances:
                # Skinned geometry
                if isinstance(instance, ScwControllerInstance):
                    gltf_node.mesh, gltf_node.skin = self._instantiate_skinned_mesh_instance(instance, nodes)  # type: ignore

                # Geometry
                elif isinstance(instance, ScwGeometryInstance):
                    gltf_node.mesh = self._instantiate_mesh_instance(instance)  # type: ignore

            # TODO: Animation
            if len(node.frames) > 1:
                pass

        self.gltf.data.nodes = gltf_nodes

    def _create_fallback_material(self, name: str):
        gltf_material = Material(
            alpha_cutoff=None,
            alpha_mode=None,
            double_sided=None,
            emissive_factor=None,
            emissive_texture=None,
            extras=None,
            name=name,
            normal_texture=None,
            occlusion_texture=None,
            pbr_metallic_roughness=None,
            extensions=None,
        )

        self.imported_materials.append(name)
        self.gltf.data.materials.append(gltf_material)

    def _import_material(self, material: ScwMaterial):
        float_vectors: dict = {}
        floats: dict = {}
        textures: dict = {}

        def import_color(name: str, color: ScwColor):
            float_vectors[name] = color.values

        def import_value(name: str, value: float):
            floats[name] = value

        def import_texture(name: str, texture: str | None):
            if texture is None:
                import_color(f"{name}Tex2D", ScwColor())
                return

            textures[f"{name}Tex2D"] = texture

        def import_surface(name: str, texture: ScwTexture):
            if isinstance(texture.surface, ScwColor):
                import_color(name, texture.surface)
            else:
                import_color(name, ScwColor())

            if isinstance(texture.surface, str):
                import_texture(name, texture.surface)

        import_color("ambient", material.ambient)
        import_surface("diffuse", material.diffuse)
        import_surface("specular", material.specular)
        import_texture("stencil", material.stencil_tex)
        import_texture("normal", material.normal_tex)
        import_surface("colorize", material.colorize)
        import_texture("emission", material.opacity_tex)
        import_value("opacity", material.opacity)
        import_value("cutout", material.cutout)
        import_texture("lightmap", material.diffuse_lightmap)
        import_texture("lightmapSpecular", material.specular_lightmap)
        import_texture("lightmapBaked", material.baked_lightmap)
        import_color("clipPlane", material.clip_plane)

        sc_material = {
            "blendMode": material.blend_mode,
            "constants": material.shader_define.as_list,
            "name": material.name,
            "shader": material.shader,
            "variables": {
                "floatVectors": float_vectors,
                "floats": floats,
                "textures": textures,
            },
        }

        gltf_material = Material(
            alpha_cutoff=None,
            alpha_mode=None,
            double_sided=None,
            emissive_factor=None,
            emissive_texture=None,
            extras=None,
            name=material.name,
            normal_texture=None,
            occlusion_texture=None,
            pbr_metallic_roughness=None,
            extensions={glTF_material_extension_name: sc_material},
        )

        self.imported_materials.append(material.name)
        self.gltf.data.materials.append(gltf_material)

    def _read_chunks(self, data: BinaryReader):
        while True:
            length = data.read_int32()
            signature = data.read_bytes(4)
            position = data.pos()
            if 0 > length:
                # raise ImportError("SCW Chunk has negative length")
                continue

            match signature:
                case b"HEAD":
                    chunk = data.read_struct(ScwHeader)
                    self._import_header(chunk)

                case b"MATE":
                    chunk = data.read_struct(ScwMaterial, version=self.version)
                    self._import_material(chunk)

                case b"GEOM":
                    chunk = data.read_struct(ScwGeometry, version=self.version)
                    self._import_mesh(chunk)

                case b"NODE":
                    chunk = data.read_struct(ScwNodes, version=self.version)
                    self._import_nodes(chunk)

                case b"WEND":
                    return

                case _:
                    self.gltf.log.warning(
                        f"Unknown SCW chunk {signature.decode("ascii")}"
                    )

            data.seek(position + length + 4)

    def read(self):
        if not isfile(self.filename):
            raise ImportError("Please select a file")

        with open(self.filename, "rb") as f:
            content = memoryview(f.read())

        data = BinaryReader(content, Endian.BIG)
        if data.read_bytes(4) != b"SC3D":
            raise ImportError("Invalid Supercell World file")

        self.gltf.data = Gltf(
            accessors=[],
            animations=[],
            asset=None,
            buffers=[],
            buffer_views=[],
            cameras=[],
            extensions=None,
            extensions_required=[],
            extensions_used=[glTF_material_extension_name],
            extras=None,
            images=[],
            materials=[],
            meshes=[],
            nodes=[],
            samplers=[],
            scene=None,
            scenes=[],
            skins=[],
            textures=[],
        )
        self._read_chunks(data)
