from ..com.utilities.mixin import MixinClass
from .components.common import CommonExporter
from .components.component import glTF2BaseExporterComponent
from .components.materials import MaterialExporter
from .components.mesh import MeshExporter

from io_scene_gltf2.io.com.gltf2_io_extensions import Extension


class glTF2ExportUserExtension(
    MeshExporter,
    MaterialExporter,
    CommonExporter,
    glTF2BaseExporterComponent,
    MixinClass,
):
    mixinRoot = True

    def __init__(self):
        super().__init__()

        # We need to wait until we create the gltf2UserExtension to import the gltf2 modules
        # Otherwise, it may fail because the gltf2 may not be loaded yet
        self.Extension = Extension

    def pre_export_hook(self, export_settings):
        self("pre_export_hook", export_settings)

    def gather_mesh_hook(
        self,
        gltf2_mesh,
        blender_mesh,
        blender_object,
        vertex_groups,
        modifiers,
        materials,
        export_settings,
    ):
        self(
            "gather_mesh_hook",
            gltf2_mesh,
            blender_mesh,
            blender_object,
            vertex_groups,
            modifiers,
            materials,
            export_settings,
        )

    def gather_material_hook(
        self,
        gltf2_material,
        blender_material,
        export_settings,
    ):
        self("gather_material_hook", gltf2_material, blender_material, export_settings)

    def gather_gltf_extensions_hook(self, gltf, export_settings):
        self("gather_gltf_extensions_hook", gltf, export_settings)

    def vtree_before_filter_hook(self, vtree, export_settings):
        self("vtree_before_filter_hook", vtree, export_settings)

    def gather_joint_hook(self, node, blender_bone, export_settings):
        self("gather_joint_hook", node, blender_bone, export_settings)
