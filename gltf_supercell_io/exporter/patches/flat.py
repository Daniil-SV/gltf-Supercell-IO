import struct
import sys
import traceback

import bpy
from io_scene_gltf2.blender.exp.export import __write_file as base_write_file

from ...com.flatbuffer import serialize_glb_json
from ...com.utilities.patcher import Patch


def save_gltf(gltf: dict, export_settings: dict, glb_buffer: bytes):
    gltf_data = serialize_glb_json(gltf)

    if export_settings["gltf_format"] != "GLB":
        export_settings["log"].error(
            "Odin output supports binary files only! Please, change gltf format to binary in your export settings, or disable Supercell export plugin"
        )
        return

    binary = glb_buffer

    length_gltf = len(gltf_data)
    spaces_gltf = (4 - (length_gltf & 3)) & 3
    length_gltf += spaces_gltf

    length_bin = len(binary)
    zeros_bin = (4 - (length_bin & 3)) & 3
    length_bin += zeros_bin

    length = 12 + 8 + length_gltf
    if length_bin > 0:
        length += 8 + length_bin

    with open(export_settings["gltf_filepath"], "wb") as file:
        # Header (Version 2)
        file.write(b"glTF")
        file.write(struct.pack("I", 2))
        file.write(struct.pack("I", length))

        # Chunk 0 (FLA2)
        file.write(struct.pack("I", length_gltf))
        file.write(b"FLA2")
        file.write(gltf_data)
        file.write(b" " * spaces_gltf)

        # Chunk 1 (BIN)
        if length_bin > 0:
            file.write(struct.pack("I", length_bin))
            file.write(b"BIN\0")
            file.write(binary)
            file.write(b"\0" * zeros_bin)

        file.close()

    return True


def write_file(json, buffer, export_settings):
    props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore
    if not props.enabled or not props.use_odin or props.debug_output:
        return base_write_file(json, buffer, export_settings)

    try:
        save_gltf(json, export_settings, buffer)

    except AssertionError as e:
        _, _, tb = sys.exc_info()
        traceback.print_tb(tb)  # Fixed format
        tb_info = traceback.extract_tb(tb)
        for tbi in tb_info:
            _filename, line, _func, text = tbi
            export_settings["log"].error(
                f"An error occurred on line {line} in statement {text}"
            )
        export_settings["log"].error(str(e))
        raise


flat_glb_output = Patch(
    "flat glb writer",
    module_path="io_scene_gltf2.blender.exp.export",
    target_method="__write_file",
    function=write_file,
)
