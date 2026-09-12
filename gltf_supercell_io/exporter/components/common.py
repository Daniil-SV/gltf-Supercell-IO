from ..patches.buffers import clear_buffer_cache
from .component import glTF2BaseExporterComponent, requires_extension, to_dict
from ...com import glTF_material_extension_name, glTF_extension_name
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
from io_scene_gltf2.io.com.constants import ComponentType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import Gltf

# Supercell's FlatBuffer glTF loader uses this high-bit flag to identify
# inverse-bind-matrix accessors.  The low 16 bits retain the glTF component
# type (FLOAT, 0x1406), making the emitted value 0x11406.
SC_ACCESSOR_INVERSE_BIND_MATRICES = 0x00010000


class CommonExporter(glTF2BaseExporterComponent):
    def gather_odin_nodes(self, gltf: "Gltf"):
        nodes = gltf.nodes or []
        parent_of = {}
        for i, node in enumerate(nodes):
            for child_idx in node.children or []:
                parent_of[child_idx] = i

        for i, node in enumerate(nodes):
            if node.extensions is None:
                node.extensions = {}

            extension = node.extensions.get(glTF_extension_name)
            if extension is None:
                extension = {}
                node.extensions[glTF_extension_name] = extension

            extension["parent"] = parent_of.get(i)

        for node in nodes:
            node.children = None

    def gather_odin_skin(self, gltf):
        # Apply Supercell's inverse-bind-matrix accessor flag
        accessors = gltf.accessors or []
        for skin in gltf.skins or []:
            skin.name = None
            accessor_index = skin.inverse_bind_matrices
            if accessor_index is None:
                continue

            accessor = accessors[accessor_index]
            if accessor.component_type != ComponentType.Float:
                continue

            accessor.component_type = (
                int(accessor.component_type) | SC_ACCESSOR_INVERSE_BIND_MATRICES
            )

    def build_odin_buffer(self):
        # At this point we need to gather all odin buffers to single buffer blob
        # First comes index buffer, accessor already contains valid offset so we don't need to do anything extra with them
        self.odin_view.data += self.index_buffer

        # Then comes vertex data layer
        self.odin_view.data += self.vertex_buffer

    def gather_odin_extension(self, gltf: "Gltf"):
        if gltf.extensions is None:
            gltf.extensions = {}

        extension: dict = gltf.extensions.get(glTF_extension_name, {})

        # Assign data blob to odin descriptor
        extension["bufferView"] = self.odin_view

        gltf.extensions[glTF_extension_name] = Extension(
            glTF_extension_name, extension, True
        )

    def serialize_odin_skin(self, gltf):
        # Serialize bounds for skin joints
        for skin in gltf.skins or []:
            skin.name = None
            bounds: list = skin.extensions[glTF_extension_name]["bounds"]
            skin.extensions[glTF_extension_name]["bounds"] = [
                bound.as_flat_list() for bound in bounds
            ]

    def serialize_odin_mesh(self, gltf: "Gltf"):
        if glTF_extension_name not in gltf.extensions:
            return

        extension = gltf.extensions[glTF_extension_name].extension
        descriptors = extension.get("meshDataInfos")
        if descriptors is None:
            return

        extension["meshDataInfos"] = [to_dict(descriptor) for descriptor in descriptors]

    @requires_extension
    def gather_gltf_hook(self, active_scene_idx, scenes, animations, export_settings):
        if self.properties.use_odin:
            self.build_odin_buffer()

    @requires_extension
    def gather_gltf_extensions_hook(self, gltf, export_settings):
        if self.properties.use_odin:
            # Should add odin parenting only after whole gltf is constructed
            self.gather_odin_nodes(gltf)

            # Add buffer view reference to extension root
            self.gather_odin_extension(gltf)

            # Serialize all odin descriptors to dict before it goes to serializer
            self.serialize_odin_mesh(gltf)

            # Then serialize skin extensions
            self.serialize_odin_skin(gltf)

        gltf.asset.generator += " | Supercell-IO Exporter by DaniilSV"

    @requires_extension
    def pre_export_hook(self, export_settings: dict):
        if not self.properties.legacy_materials:
            export_settings[glTF_material_extension_name] = []

    def post_export_hook(self, export_settings: dict):
        clear_buffer_cache()
