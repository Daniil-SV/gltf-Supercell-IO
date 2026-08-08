from bpy.props import StringProperty
from bpy.types import FileHandler, Operator
from bpy_extras.io_utils import ImportHelper, poll_file_object_drop
from io_scene_gltf2 import ImportGLTF2, ExportGLTF2_Base
from io_scene_gltf2.blender.imp.blender_gltf import BlenderGlTF
from . import ScwFile


class ImportSCW(Operator, ExportGLTF2_Base, ImportHelper):  # type: ignore
    bl_idname = "import_scene.scw"
    bl_label = "Import SCW"

    __annotations__ = dict(ImportGLTF2.__annotations__)

    filter_glob: StringProperty(default="*.scw", options={"HIDDEN"})

    def draw(self, context):
        return ImportGLTF2.draw(self, context)  # type: ignore

    def invoke(self, context, event):  # type: ignore
        return ImportGLTF2.invoke(self, context, event)  # type: ignore

    def unit_import(self, filename, import_settings):
        import time

        try:
            scw = ScwFile(filename, import_settings)
            scw.read()

            scw.gltf.log.info("Data are loaded, start creating Blender stuff")

            start_time = time.time()
            BlenderGlTF.create(scw.gltf)
            elapsed_s = "{:.2f}s".format(time.time() - start_time)
            scw.gltf.log.info("glTF import finished in " + elapsed_s)

            # Display popup log, if any
            for message_type, message in scw.gltf.log.messages():  # type: ignore
                self.report({message_type}, message)

            scw.gltf.log.flush()

            return {"FINISHED"}

        except ImportError as e:
            self.report({"ERROR"}, e.args[0])
            return {"CANCELLED"}

    def import_gltf2(self, context):
        return ImportGLTF2.import_gltf2(self, context)  # type: ignore

    def execute(self, context):  # type: ignore
        return self.import_gltf2(context)


class IO_FH_scw(FileHandler):
    bl_idname = "IO_FH_scw"
    bl_label = "Supercell World"
    bl_import_operator = "import_scene.scw"
    bl_file_extensions = ".scw"

    @classmethod
    def poll_drop(cls, context):
        poll_file_object_drop(context)
        return True


def scw_func_import(self, context):
    self.layout.operator(ImportSCW.bl_idname, text="Supercell World (.scw)")
