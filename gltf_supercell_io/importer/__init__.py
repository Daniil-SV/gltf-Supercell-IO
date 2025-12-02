import bpy

from ..com import glTF_extension_name, glTF_material_extension_name
from ..com.odin.constants import OdinAttributeFormat, OdinAttributeType
from ..com.odin.attribute import OdinAttribute
from ..com.materials import ScShaderMaterial

from ..com.shader.pressets import ShaderPreset, ShaderPresetType
from ..com.shader.unlit import UnlitPreset

from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter, ImportError
from io_scene_gltf2.io.com.gltf2_io import Accessor, Material, Node, Mesh, MeshPrimitive, Scene, Skin
from io_scene_gltf2.blender.imp.vnode import VNode
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData

from typing import List
import numpy as np


class glTF2ImportUserExtension:
    def __init__(self):
        self.properties = bpy.context.scene.glTFSupercellImporterProperties
        self.extensions = [
            # Odin extension with custom meshes and animations store method
            Extension(name=glTF_extension_name, extension={}, required=True),
            
            # Custom materials
            Extension(name=glTF_material_extension_name, extension={}, required=False)
        ]
        
    def valid_gltf(self, gltf: glTFImporter):
        required = gltf.data.extensions_required or []
        used = gltf.data.extensions_used or []
        has_extension = glTF_extension_name in required
        has_shader = glTF_material_extension_name in used
        
        return has_extension or has_shader

    def process_accessors(self, gltf: glTFImporter):
        """Supercell uses special component types for some accessors to optimize gpu memory usage, which is not standard and needs to be converted to normal here"""
        # Exclusive Accessor Component Types
        # 1 - Float Vector 3
        # 2 - Float Vector 4
        # 3 - Matrix4x4

        accessors: List[Accessor] = gltf.data.accessors
        for accessor in accessors:
            accessor.component_type = accessor.component_type & 0x0000FFFF

    def get_extension_descriptor(self, gltf: glTFImporter) -> dict | None:
        extensions: dict = gltf.data.extensions
        if (extensions is None):
            return None

        return extensions.get(glTF_extension_name, None)

    def move_materials(self, gltf: glTFImporter):
        """Supercell stores their materials in extensions, so we need to move them to the main materials list if there is a need"""
        descriptor = self.get_extension_descriptor(gltf)
        if (descriptor is None):
            return

        materials = descriptor.get("materials")
        if (materials is None):
            return

        gltf.data.materials = [
            Material.from_dict({"extensions": {glTF_material_extension_name: material}}) for material in materials
        ]

    def process_nodes_extension(self, gltf: glTFImporter):
        """Repairs gltf children relation indexing based on classic parent indexing stored in node extensions"""
        nodes: List[Node] = gltf.data.nodes or []

        childrens: dict[int, list[int]] = {}

        def add_child(idx: int, parent_idx: int):
            if (parent_idx not in childrens):
                childrens[parent_idx] = []
            childrens[parent_idx].append(idx)

        for i, node in enumerate(nodes):
            extensions = node.extensions
            if (extensions is None):
                continue

            descriptor = extensions.get(glTF_extension_name)
            if (descriptor is None):
                continue

            parent = descriptor.get("parent")
            add_child(i, parent)

        for idx, children in childrens.items():
            nodes[idx].children = children

    def do_final_fixups(self, gltf: glTFImporter):
        """Very often Supercell glTF files have missing fields that are required by the importer, this function adds them back"""

        root_nodes = []
        nodes: List[Node] = gltf.data.nodes or []
        skins: List[Skin] = gltf.data.skins or []

        # Fix for scene nodes
        if (gltf.data.scenes is None):
            childrens = set()
            for node in nodes:
                if node.children is None:
                    continue

                childrens.update(node.children)

            root_nodes = [i for i in range(len(nodes)) if i not in childrens]
            gltf.data.scenes = [Scene(None, None, None, root_nodes)]
        else:
            for scene in gltf.data.scenes:
                if (scene.nodes is None):
                    root_nodes = scene.nodes
                    break

        if (self.properties.single_skeleton and len(root_nodes)):
            if (len(root_nodes) == 1):
                for skin in skins:
                    skin.skeleton = root_nodes[0]
            else:
                children_mapping = {key: [] for key in root_nodes}
                def visit(key: int, node_index: int):
                    childrens = gltf.data.nodes[node_index].children or []
                    
                    for idx in childrens:
                        children_mapping[key].append(idx)
                        visit(key, idx)
                
                for key in root_nodes:
                    visit(key, key)
                
                for skin in skins:
                    for key, childrens in children_mapping.items():
                        if (any(i in childrens for i in skin.joints or [])):
                            skin.skeleton = key
                            break

        gltf.data.meshes = gltf.data.meshes or []

    def setup_settings(self, gltf: glTFImporter):
        # Why tf this exists at all
        gltf.import_settings['disable_bone_shape'] = True

        # May have other values in some older versions
        gltf.import_settings['bone_heuristic'] = 'BLENDER'

        # Also very useful thing for mesh
        gltf.import_settings['merge_vertices'] = True

    def gather_import_gltf_before_hook(self, gltf: glTFImporter):
        if (not self.valid_gltf(gltf)):
            return

        self.process_accessors(gltf)
        self.move_materials(gltf)

        self.process_nodes_extension(gltf)
        self.do_final_fixups(gltf)

        if (self.properties.better_settings):
            self.setup_settings(gltf)

        # Shared cache for all meshes import operations
        gltf.supercell_vertex_cache = {}
        gltf.supercell_vertex_accessor_offset = 0

    def gather_import_node_before_hook(self, vnode: VNode, node: Node | None, gltf: glTFImporter):
        """Some nodes (especially in animation files) may have invalid indices, we need to clean them up to avoid errors"""
        if (not self.valid_gltf(gltf)):
            return

        if (node is None):
            return

        meshes_count = len(gltf.data.meshes or [])
        if (node.mesh is not None):
            if (node.mesh >= meshes_count):
                node.mesh = None
                vnode.type = VNode.DummyRoot
                vnode.mesh_node_idx = None

    def decode_mesh_attribute(self, gltf: glTFImporter, buffer_idx: int, attribute: dict, offset: int, stride: int) -> tuple[str, np.array]:
        attribute_type = OdinAttributeType(attribute.get("index"))
        attribute_format = OdinAttributeFormat(attribute.get("format"))
        element_offset = attribute.get("offset", 0)
        buffer_data = BinaryData.get_buffer_view(gltf, buffer_idx)

        name = OdinAttributeType.to_attribute_name(attribute_type)
        data = OdinAttribute(
            buffer_data, attribute_format, offset, element_offset, stride
        )

        return (name, data)

    def decode_mesh_info(self, gltf: glTFImporter, idx: int):
        descriptor = self.get_extension_descriptor(gltf) or {}
        mesh_infos: list[dict] = descriptor.get("meshDataInfos")
        buffer_idx = descriptor.get("bufferView")
        if (mesh_infos is None or buffer_idx is None):
            raise ImportError("Missing Supercell glTF mesh data")

        # Prepare cache
        attributes = {}

        mesh_info = mesh_infos[idx]
        vertex_descriptors = mesh_info.get("vertexDescriptors")
        for descriptors in vertex_descriptors:
            offset = descriptors.get("offset", 0)
            stride = descriptors.get("stride", 0)

            for attribute in descriptors.get("attributes", []):
                name, data = self.decode_mesh_attribute(
                    gltf, buffer_idx, attribute, offset, stride)
                attributes[name] = data

        gltf.supercell_vertex_cache[idx] = attributes

    def decode_primitive(self, gltf: glTFImporter, primitive: MeshPrimitive):
        extensions = primitive.extensions
        if (extensions is None):
            return

        descriptor = extensions.get(glTF_extension_name)
        if (descriptor is None):
            return

        mesh_info_idx = descriptor.get("meshDataInfoIndex")
        if (mesh_info_idx is None):
            return

        if (mesh_info_idx not in gltf.supercell_vertex_cache):
            self.decode_mesh_info(gltf, mesh_info_idx)

        # MEGA HACK: instead of writing writing back to buffer and then to accessors and blah blah blah...
        # We do next magic:
        # 1. Create custom class that will "emulate" np.array for attributes (basically just a wrapper with __getitem__ method)
        # that will have streaming-like behavior to avoid multiple indices reading in order to creating usual fixed-size numpy arrays
        # We will pass this streaming attribute to glTF importer directly
        # 2. To actually pass our custom attribute data, we will use existing cache system
        # We can just create our own accessor indices to which importer will ask data from,
        # so we can set it in advance in caching pool it will return our custom streaming attribute
        # Profit 500%

        primitive.attributes = {}
        for name, data in gltf.supercell_vertex_cache[mesh_info_idx].items():
            fake_accessor_idx = gltf.supercell_vertex_accessor_offset
            primitive.attributes[name] = fake_accessor_idx
            gltf.decode_accessor_cache[fake_accessor_idx] = data
            gltf.accessor_cache[fake_accessor_idx] = data

            gltf.supercell_vertex_accessor_offset += 1

    def gather_import_mesh_options(self, mesh_options, pymesh: Mesh, skin_idx, gltf: glTFImporter):
        """Please khronos i need this. My glTF importer is kinda homeless"""
        if (not self.valid_gltf(gltf)):
            return

        # sooo... since exporter settings up some settings at top-level of mesh conversion
        # we need to decode all mesh infos here to have them ready for primitives decoding
        # not a good place but... there will be no peaceful solution

        gltf.supercell_vertex_accessor_offset = len(gltf.data.accessors or [])
        primitives: List[MeshPrimitive] = pymesh.primitives or []
        for primitive in primitives:
            self.decode_primitive(gltf, primitive)

    def gather_import_material_before_hook(self, gltf_material: Material, vertex_color, gltf: glTFImporter):
        if (not self.valid_gltf(gltf)):
            return
        
        extensions = gltf_material.extensions = gltf_material.extensions or {}
        descriptor: dict = extensions.get(glTF_material_extension_name)
        if (descriptor is None):
            return
        
        material = ScShaderMaterial()
        material.from_dict(gltf, descriptor)
        extensions[glTF_material_extension_name] = material
        gltf_material.name = material.name
        
    def gather_import_material_after_hook(self, gltf_material: Material, vertex_color, blender_mat: bpy.types.Material, gltf: glTFImporter):
        if (not self.valid_gltf(gltf)):
            return
        
        extensions = gltf_material.extensions or {}
        material: ScShaderMaterial = extensions.get(glTF_material_extension_name)
        if (material is None):
            return
        
        preset: ShaderPreset = None
        match(self.properties.shader_preset):
            case ShaderPresetType.UNLIT:
                preset = UnlitPreset(material, blender_mat)
            case _:
                raise NotImplementedError()
        
        # Cleanup material from glTF fallback and prepare for our own processing
        gltf_material.pbr_metallic_roughness.blender_nodetree = None
        gltf_material.pbr_metallic_roughness.blender_mat = None
        if not blender_mat.node_tree:
            blender_mat.use_nodes = True
            
        tree = blender_mat.node_tree
        tree.nodes.clear()
        
        # Selected preset creation
        preset.create_material()
        
    def gather_import_scene_after_nodes_hook(self, gltf_scene, blender_scene: bpy.types.Scene, gltf):
        if (not self.valid_gltf(gltf)):
            return
        
        if (self.properties.adjust_colorspace):
            blender_scene.view_settings.view_transform = "Raw"