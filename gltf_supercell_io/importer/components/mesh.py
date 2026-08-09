from typing import List, TYPE_CHECKING
from .component import glTF2BaseImporterComponent, requires_extension
from ...com.odin.constants import OdinAttributeFormat, OdinAttributeType
from ...com.odin.attribute import OdinAttribute
from ...com import glTF_extension_name

from io_scene_gltf2.io.imp.gltf2_io_gltf import ImportError
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
from io_scene_gltf2.blender.imp.material import BlenderMaterial

if TYPE_CHECKING:
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
    from io_scene_gltf2.io.com.gltf2_io import MeshPrimitive


class OdinMeshImporter(glTF2BaseImporterComponent):
    def decode_mesh_attribute(
        self,
        gltf: "glTFImporter",
        buffer_idx: int,
        attribute: dict,
        offset: int,
        stride: int,
    ):
        attribute_type = OdinAttributeType(attribute.get("index"))
        attribute_format = OdinAttributeFormat(attribute.get("format"))
        element_offset = attribute.get("offset", 0)
        buffer_data = BinaryData.get_buffer_view(gltf, buffer_idx)

        name = OdinAttributeType.to_attribute_name(attribute_type)
        data = OdinAttribute(
            buffer_data,
            attribute_format,
            attribute_type,
            offset,
            element_offset,
            stride,
        )

        return (name, data)

    def decode_mesh_info(self, gltf: "glTFImporter", idx: int):
        descriptor = self.get_extension(gltf) or {}
        mesh_infos: list[dict] = descriptor.get("meshDataInfos")  # type: ignore
        buffer_idx = descriptor.get("bufferView")
        if mesh_infos is None or buffer_idx is None:
            raise ImportError("Missing Supercell glTF mesh data")

        # Prepare cache
        attributes = {}

        mesh_info = mesh_infos[idx]
        vertex_descriptors: List[dict] = mesh_info.get(
            "vertexDescriptors"
        )  # type: ignore
        for descriptors in vertex_descriptors:
            offset = descriptors.get("offset", 0)
            stride = descriptors.get("stride", 0)

            for attribute in descriptors.get("attributes", []):
                name, data = self.decode_mesh_attribute(
                    gltf, buffer_idx, attribute, offset, stride
                )
                attributes[name] = data

        gltf.supercell_vertex_cache[idx] = attributes  # type: ignore

    def handle_vertex_color(self, gltf: "glTFImporter", primitive: "MeshPrimitive"):
        # TRICK: gltf importer proceeds vertex color kinda... strangely.
        # It creates separate material specifically if there is COLOR_0 attribute.
        # Should i say that this thing breaks EVERYTHING?
        # So... We need to trick gltf importer and somehow avoid creating
        # this stupid materials and also import this color attributes, so user can decide yourself what to do with that
        # or in the future i will add custom processing anyway
        # So I came up with the idea that we need to get ahead of
        # gltf importer and import materials manually, filling in all variations as needed

        # Checking if primitive has color and material at all
        if "COLOR_0" in primitive.attributes and primitive.material is not None:
            pymaterial = gltf.data.materials[primitive.material]
            mat = pymaterial.blender_material

            # Create ahead of time
            if None not in mat:
                BlenderMaterial.create(gltf, primitive.material, None)

            # Fill material variants dict
            i = 0
            while ("COLOR_%d" % i) in primitive.attributes:
                mat[f"COLOR_{i}"] = mat[None]
                i += 1

    def decode_primitive(self, gltf: "glTFImporter", primitive: "MeshPrimitive"):
        extensions = primitive.extensions
        if extensions is None:
            return

        descriptor = extensions.get(glTF_extension_name)
        if descriptor is None:
            return

        mesh_info_idx = descriptor.get("meshDataInfoIndex")
        if mesh_info_idx is None:
            return

        if mesh_info_idx not in gltf.supercell_vertex_cache:  # type: ignore
            self.decode_mesh_info(gltf, mesh_info_idx)

        # MEGA HACK: instead of writing back to buffer and then to accessors and blah blah blah...
        # We do next magic:
        # 1. Create custom class that will "emulate" np.array for attributes (basically just a wrapper with __getitem__ method)
        # that will have streaming-like behavior to avoid multiple indices reading in order to creating usual fixed-size numpy arrays
        # We will pass this streaming attribute to glTF importer directly
        # 2. To actually pass our custom attribute data, we will use existing cache system
        # We can just create our own accessor indices to which importer will ask data from,
        # so we can set it in advance in caching pool it will return our custom streaming attribute
        # Profit 500%

        primitive.attributes = {}

        for name, data in gltf.supercell_vertex_cache[mesh_info_idx].items():  # type: ignore # noqa
            fake_accessor_idx = gltf.supercell_vertex_accessor_offset  # type: ignore
            primitive.attributes[name] = fake_accessor_idx
            gltf.decode_accessor_cache[fake_accessor_idx] = data
            gltf.accessor_cache[fake_accessor_idx] = data

            gltf.supercell_vertex_accessor_offset += 1  # type: ignore

    @requires_extension
    def gather_import_mesh_options(
        self,
        mesh_options,
        pymesh,
        skin_idx,
        gltf,
    ):

        # Story:
        # Some of the bones has scale property in nodes (finger bones from grom_geo.glb Brawl Stars, for example)
        # Well, most likely optimizer skill issue
        # It`s works like this: During the rendering process, renderer multiplying nodes scale and the inverse matrix,
        # which is resulting normal looking transformation,
        # but for blender this behavior is very inconvenient and critical
        # This exact option prevents mesh from transformation with most of the time broken scale value
        # We will handle this case separately later
        # BUT! apply skin to scw files, it would be useful with its mesh bind matrices
        if not self.properties.importing_scw:
            mesh_options.skin_into_bind_pose = False

        # Sooo... since exporter setups some settings at top-level of mesh conversion
        # we need to decode all mesh infos here to have them ready for primitives decoding
        # not a good place but... there will be no peaceful solution
        gltf.supercell_vertex_accessor_offset = len(  # type: ignore #noqa
            gltf.data.accessors or []
        )

        primitives: List["MeshPrimitive"] = pymesh.primitives or []
        for primitive in primitives:
            self.decode_primitive(gltf, primitive)
            self.handle_vertex_color(gltf, primitive)
