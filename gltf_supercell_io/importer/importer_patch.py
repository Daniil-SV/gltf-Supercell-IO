import struct
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from ..com.flatbuffer import deserialize_glb_json
import sys
import types

TARGET_MODULE = "io_scene_gltf2.io.imp.gltf2_io_gltf"
TARGET_CLASS = "glTFImporter"
TARGET_METHOD = "load_glb"


def load_glb(self: glTFImporter, content: bytes):
    """Load binary glb."""
    magic = content[:4]
    if magic != b'glTF':
        raise ImportError("This file is not a glTF/glb file")

    version, file_size = struct.unpack_from('<II', content, offset=4)
    if version != 2:
        raise ImportError("GLB version must be 2; got %d" % version)
    if file_size != len(content):
        raise ImportError("Bad GLB: file size doesn't match")

    glb_buffer = None
    offset = 12  # header size = 12

    # JSON/FLAT chunk is first
    name, length, data, offset = self.load_chunk(content, offset)
    if (name == b'FLA2'):
        gltf = deserialize_glb_json(data)
    elif (name == b'JSON'):
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


if TARGET_MODULE not in sys.modules:
    fake_module = types.ModuleType(TARGET_MODULE)
    sys.modules[TARGET_MODULE] = fake_module


def patch_importer():
    try:
        mod = __import__(TARGET_MODULE, fromlist=[TARGET_CLASS])
        cls = getattr(mod, TARGET_CLASS)

        setattr(cls, TARGET_METHOD, load_glb)
    except Exception as e:
        print(f"[SC IO] Failed to patch: {e}")
