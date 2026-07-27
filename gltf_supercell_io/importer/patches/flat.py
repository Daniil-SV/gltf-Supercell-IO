import struct
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from ...com.flatbuffer import deserialize_glb_json
from ...com.utilities.patcher import Patch


def load_glb(self: "glTFImporter", content: bytes):
    """Load binary glb."""
    magic = content[:4]
    if magic != b"glTF":
        raise ImportError("This file is not a glTF/glb file")

    version, file_size = struct.unpack_from("<II", content, offset=4)
    if version != 2:
        raise ImportError("GLB version must be 2; got %d" % version)
    if file_size != len(content):
        raise ImportError("Bad GLB: file size doesn't match")

    glb_buffer = None
    offset = 12  # header size = 12

    # JSON/FLAT chunk is first
    name, length, data, offset = self.load_chunk(content, offset)
    if name == b"FLA2":
        gltf = deserialize_glb_json(data)
    elif name == b"JSON":
        gltf = glTFImporter.load_json(data)
    else:
        raise ImportError("Bad GLB: first chunk not JSON")

    # BIN chunk is second (if it exists)
    if offset < len(content):
        name, length, data, offset = self.load_chunk(content, offset)
        if name == b"BIN\0":
            if length != len(data):
                raise ImportError("Bad GLB: length of BIN chunk doesn't match")
            glb_buffer = data

    return gltf, glb_buffer


flatbuffer_glb = Patch(
    "flatbuffer gltf",
    module_path="io_scene_gltf2.io.imp.gltf2_io_gltf",
    target_class="glTFImporter",
    target_method="load_glb",
    function=load_glb,
)
