import bpy
import sys
import traceback
from io_scene_gltf2.blender.exp.export import __postprocess_with_gltfpack
from ...com.utilities.patcher import Patch


def write_gltf(json: dict, buffer: bytes):
    pass


def write_file(fallback):
    """Patch the exporter to use the custom write_gltf function"""

    def __write_file(json, buffer, export_settings):
        props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore
        if not props.optimize_json:
            return fallback(json, buffer, export_settings)

        try:
            write_gltf(json, buffer)
            if export_settings["gltf_use_gltfpack"]:
                __postprocess_with_gltfpack(export_settings)

        except AssertionError as e:
            _, _, tb = sys.exc_info()
            traceback.print_tb(tb)  # Fixed format
            tb_info = traceback.extract_tb(tb)
            for tbi in tb_info:
                filename, line, func, text = tbi
                export_settings["log"].error(
                    "An error occurred on line {} in statement {}".format(line, text)
                )
            export_settings["log"].error(str(e))
            raise e

    return __write_file


flat_glb_output = Patch(
    "flat glb writer",
    module_path="io_scene_gltf2.blender.exp.export",
    target_method="__write_file",
    function=write_file,
)
