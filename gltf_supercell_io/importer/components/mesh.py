import numpy as np
from typing import List, TYPE_CHECKING
from .component import glTF2BaseImporterComponent, requires_extension
from ...com.odin.constants import OdinAttributeFormat, OdinAttributeType
from ...com.odin.attribute import OdinAttributeReader
from ...com import glTF_extension_name

from io_scene_gltf2.io.imp.gltf2_io_gltf import ImportError
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
from io_scene_gltf2.blender.imp.material import BlenderMaterial

if TYPE_CHECKING:
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
    from io_scene_gltf2.io.com.gltf2_io import MeshPrimitive


class OdinMeshImporter(glTF2BaseImporterComponent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache: dict[int, dict] = {}
        self.accessor_offset = 0

    @requires_extension
    def gather_import_gltf_before_hook(self, gltf: "glTFImporter"):
        # Importer components outlive a single glTF import. Attribute readers
        # retain a view of the source buffer, so they must never be reused for
        # a later file that happens to use the same meshDataInfoIndex.
        self.cache.clear()
        self.accessor_offset = 0

    def decode_mesh_attribute(
        self,
        gltf: "glTFImporter",
        buffer_idx: int,
        attribute: dict,
        offset: int,
        stride: int,
    ):
        attribute_type = OdinAttributeType(attribute.get("name"))
        attribute_format = OdinAttributeFormat(attribute.get("format"))
        element_offset = attribute.get("offset", 0)
        buffer_data: memoryview | None = BinaryData.get_buffer_view(gltf, buffer_idx)

        name = OdinAttributeType.to_attribute_name(attribute_type)
        data = OdinAttributeReader(
            np.asarray(buffer_data),
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

        self.cache[idx] = attributes

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

    def decode_primitive(
        self,
        gltf: "glTFImporter",
        primitive: "MeshPrimitive",
    ):
        extensions = primitive.extensions
        if extensions is None:
            return

        descriptor = extensions.get(glTF_extension_name)
        if descriptor is None:
            return

        mesh_info_idx = descriptor.get("meshDataInfoIndex")
        if mesh_info_idx is None:
            return

        if mesh_info_idx not in self.cache:
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

        for name, data in self.cache[mesh_info_idx].items():
            primitive.attributes[name] = self.accessor_offset
            gltf.decode_accessor_cache[self.accessor_offset] = data
            gltf.accessor_cache[self.accessor_offset] = data

            self.accessor_offset += 1  # type: ignore

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
        self.accessor_offset = len(gltf.data.accessors or [])

        primitives: List["MeshPrimitive"] = pymesh.primitives or []
        for primitive in primitives:
            self.decode_primitive(gltf, primitive)
            self.handle_vertex_color(gltf, primitive)

    @requires_extension
    def gather_import_mesh_after_hook(self, gltf_mesh, blender_mesh, gltf):
        extensions = gltf_mesh.extensions or {}
        odin: dict | None = extensions.get(glTF_extension_name)
        if odin is None:
            return

        inverse_pretransform = odin.get("inversePretransform")
        if inverse_pretransform is None:
            return

        matrix_4x3 = np.asarray(inverse_pretransform, dtype=np.float32)
        if matrix_4x3.shape != (4, 3):
            raise ImportError("inversePretransform must be a 4x3 affine matrix")

        # Odin serializes xMatrix44 as four XYZ columns. The missing W values
        # are (0, 0, 0, 1). The game stores this matrix on the geometry and
        # applies it as part of rendering; transforming the completed Blender
        # mesh is equivalent and also lets Blender update normals correctly.
        matrix_4x4 = np.column_stack((matrix_4x3, (0.0, 0.0, 0.0, 1.0)))
        blender_mesh.transform(gltf.matrix_gltf_to_blender(matrix_4x4.ravel()))  # type: ignore
