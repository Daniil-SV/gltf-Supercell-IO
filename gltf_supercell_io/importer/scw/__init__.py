import bpy
from ...com.utilities.binary_reader import BinaryReader, Endian
from ...com.utilities.accessor import MemoryAccessor
from ..ui import glTFSupercellImporterProperties
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.imp.gltf2_io_gltf import ImportError
from io_scene_gltf2.io.com.gltf2_io import (
    Gltf,
    Node,
    Mesh,
    MeshPrimitive,
    Material,
    Skin,
    Animation,
    AnimationChannel,
    AnimationSampler,
    AnimationChannelTarget,
    Camera,
    CameraPerspective,
)
from .chunks.header import ScwHeader
from .chunks.geometry import ScwGeometry, ScwWeights
from .chunks.nodes import ScwNodes, ScwNode
from .chunks.material import ScwMaterial, Color as ScwColor, Texture as ScwTexture
from .chunks.instance import ScwInstance
from .chunks.instance.controller_instance import (
    ScwGeometryInstance,
    ScwControllerInstance,
)
from .chunks.instance.camera_instance import ScwCameraInstance
from .chunks.camera import ScwCamera
from .chunks.sub.attribute import ScwAttribute
from .chunks.sub.primitive import ScwPrimitive
from .chunks.sub.joint import ScwJoint
from os.path import isfile
from ...com import glTF_material_extension_name
from copy import copy
from dataclasses import dataclass
import numpy as np
from pathlib import Path
from math import radians
from typing import Optional, cast, Any

ANIM_CHANNELS = [("translation", 3), ("rotation", 4), ("scale", 3)]


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
        case "color":
            return "COLOR_0"
        case _:
            raise ImportError(f"Unknown SCW attribute name {name}")


class ScwFile:
    def __init__(self, filename: str, settings: dict) -> None:
        self.version = -1
        self.frame_rate = 30
        self.filename = filename
        self.gltf = glTFImporter(filename, settings)
        self.imported_meshes: dict[str, Mesh] = {}
        self.imported_materials: list[str] = []
        self.imported_skins: dict[str, tuple[ScwJoint, ...]] = {}
        self.mesh_instances: dict[CachedMeshInstance, int] = {}
        self.imported_cameras: dict[str, int] = {}
        self.properties: glTFSupercellImporterProperties = cast(
            Any, bpy.context.scene
        ).glTFSupercellImporterProperties

    def _import_header(self, header: ScwHeader):
        self.version = header.version
        self.frame_rate = header.frame_rate

        if bpy.context.scene:
            if self.properties.setup_timeline:
                bpy.context.scene.frame_start = header.frame_start
                bpy.context.scene.frame_end = header.frame_end

            if self.properties.fps_source == "SEQUENCE":
                bpy.context.scene.render.fps = header.frame_rate
            elif self.properties.fps_source == "CUSTOM":
                bpy.context.scene.render.fps = self.properties.fps_custom

        if header.materials_file is not None:
            self.properties.material_override = header.materials_file

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
                        joint.inverse_bind_matrix @ mesh.bind_matrix
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

    def _create_skin(self, name: str, nodes: ScwNodes) -> int:
        joints_idx: list[int] = []
        inv_matrices: int | None = None

        if name in self.imported_skins:
            keys = [node.name for node in nodes.nodes]
            joints = self.imported_skins[name]

            joints_idx = [keys.index(joint.name) for joint in joints]
            joints_matrices = [
                joint.inverse_bind_matrix.transposed() for joint in joints
            ]
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

    def _instantiate_mesh_instance(self, instance: ScwGeometryInstance) -> int:
        return self._instantiate_mesh(instance.target_mesh, instance.material_binding)

    def _instantiate_skinned_mesh_instance(
        self, instance: ScwControllerInstance, nodes: ScwNodes
    ) -> tuple[int, int]:
        mesh_idx = self._instantiate_mesh(
            instance.target_mesh, instance.material_binding
        )

        skin_idx = self._create_skin(instance.target_mesh, nodes)
        return (mesh_idx, skin_idx)

    def _import_node_instance(self, node: Node, instance: ScwInstance, nodes: ScwNodes):
        # Skinned geometry
        if isinstance(instance, ScwControllerInstance):
            node.mesh, node.skin = self._instantiate_skinned_mesh_instance(instance, nodes)  # type: ignore

        # Geometry
        elif isinstance(instance, ScwGeometryInstance):
            node.mesh = self._instantiate_mesh_instance(instance)  # type: ignore
            
        # Camera
        elif isinstance(instance, ScwCameraInstance):
            node.camera = self.imported_cameras[instance.camera_name]

    def _import_node_instances(
        self, instances: tuple[ScwInstance, ...], node: Node, nodes: ScwNodes
    ):
        if len(instances) == 1:
            return self._import_node_instance(node, instances[0], nodes)

        # Should create additional children node for each instance if there a few
        for i, instance in enumerate(instances):
            gltf_node = Node(
                None, [], None, None, None, None, None, None, None, None, None, None
            )

            node_name = node.name
            if isinstance(instance, ScwControllerInstance):
                node_name = f"{node.name}-contoller-{i}"
            elif isinstance(instance, ScwGeometryInstance):
                node_name = f"{node.name}-geometry-{i}"
            elif isinstance(instances, ScwCameraInstance):
                node_name = f"{node.name}-camera-{i}"

            gltf_node.name = node_name  # type: ignore
            self._import_node_instance(gltf_node, instance, nodes)
            node.children.append(len(self.gltf.data.nodes))
            self.gltf.data.nodes.append(gltf_node)

    def _get_or_create_animation(self) -> Animation:
        if len(self.gltf.data.animations) == 0:
            animation_name = Path(self.gltf.filename).stem
            animation = Animation([], None, None, animation_name, [])
            self.gltf.data.animations.append(animation)
            return animation

        return self.gltf.data.animations[0]

    def _import_node_animation_channel(
        self,
        node: ScwNode,
        target_idx: int,
        animation: Animation,
        channel_name: str,
        count: int,
    ):
        sampler_idx = len(animation.samplers)
        target = AnimationChannelTarget(None, None, target_idx, channel_name)
        channel = AnimationChannel(None, None, sampler_idx, target)

        frames_count = len(node.frames)
        timestamps = (
            np.array([frame.index for frame in node.frames], dtype=np.float32)
            / self.frame_rate
        )
        timestamps = timestamps.reshape((-1, 1))

        outputs = np.zeros((frames_count, count))
        for idx in range(frames_count):
            frame = node.frames[idx]
            values = [val for val in getattr(frame, channel_name)]
            outputs[idx] = np.array(values, dtype=np.float32)

        sampler = AnimationSampler(
            None,
            None,
            self._create_accessor(timestamps),
            None,
            self._create_accessor(outputs),
        )

        animation.channels.append(channel)
        animation.samplers.append(sampler)

    def _import_node_animation(self, node: ScwNode, node_idx: int):
        animation = self._get_or_create_animation()

        for channel, count in ANIM_CHANNELS:
            self._import_node_animation_channel(
                node, node_idx, animation, channel, count
            )

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
                gltf_node.translation = [val for val in frame.translation]  # type: ignore
                if frame.rotation is not None:
                    gltf_node.rotation = [val for val in frame.rotation]  # type: ignore

                gltf_node.scale = [val for val in frame.scale]  # type: ignore

            # Processing instances
            self._import_node_instances(node.instances, gltf_node, nodes)

            if len(node.frames) > 1:
                self._import_node_animation(node, idx)

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
        import_surface("emission", material.emission)
        import_value("opacity", material.opacity)
        import_value("cutout", material.cutout)
        import_texture("lightmap", material.diffuse_lightmap)
        import_texture("lightmapSpecular", material.specular_lightmap)
        import_texture("lightmapBaked", material.baked_lightmap)
        import_color("clipPlane", material.clip_plane)

        shader_name = Path(material.shader).with_suffix("").as_posix()
        sc_material = {
            "blendMode": material.blend_mode,
            "constants": material.shader_define.as_list,
            "name": material.name,
            "shader": shader_name,
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

    def _import_camera(self, camera: ScwCamera):
        pespective = CameraPerspective(
            camera.aspect_ratio,
            None,
            None,
            radians(camera.y_fov),
            camera.z_far,
            camera.z_near,
        )
        gltf_camera = Camera(None, None, camera.name, None, pespective, "perspective")
        gltf_camera_idx = len(self.gltf.data.cameras)
        self.imported_cameras[camera.name] = gltf_camera_idx
        self.gltf.data.cameras.append(gltf_camera)

    def _read_chunks(self, data: BinaryReader):
        while True:
            data.read_int32()  # chunk length
            signature = data.read_bytes(4)

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

                case b"CAME":
                    chunk = data.read_struct(ScwCamera, version=self.version)
                    self._import_camera(chunk)

                case b"NODE":
                    chunk = data.read_struct(ScwNodes, version=self.version)
                    self._import_nodes(chunk)

                case b"WEND":
                    return

                case _:
                    self.gltf.log.warning(
                        f"Unknown SCW chunk {signature.decode("ascii")}"
                    )

            data.read_int32()  # chunk crc32 checksum

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
