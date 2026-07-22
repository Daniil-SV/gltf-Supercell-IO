from ..com import glTF_extension_name, glTF_material_extension_name
from .components.component import glTF2BaseImporterComponent
from ..com.utilities.mixin import MixinClass
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension

from .components.common import CommonImporter
from .components.mesh import OdinMeshImporter
from .components.animation import OdinAnimationImporter
from .components.materials import SupercellShaderImporter
from .components.skin import SkinImporter

class glTF2ImportUserExtension(
    CommonImporter,
    SkinImporter,
    SupercellShaderImporter,
    OdinMeshImporter,
    OdinAnimationImporter,
    glTF2BaseImporterComponent,
    MixinClass,
):
    mixinRoot = True

    def __init__(self):
        super().__init__(root=True)

        self.extensions = [
            # Odin extension with custom meshes and animations store method
            Extension(name=glTF_extension_name, extension={}, required=True),
            # Custom materials
            Extension(name=glTF_material_extension_name, extension={}, required=False),
        ]

    def gather_import_gltf_before_hook(self, gltf):
        self("gather_import_gltf_before_hook", gltf)

    def gather_import_node_before_hook(self, vnode, node, gltf):
        self("gather_import_node_before_hook", vnode, node, gltf)

    def gather_import_mesh_options(self, mesh_options, pymesh, skin_idx, gltf):
        self("gather_import_mesh_options", mesh_options, pymesh, skin_idx, gltf)

    def gather_import_animation_before_hook(self, anim_idx, gltf):
        self("gather_import_animation_before_hook", anim_idx, gltf)

    def gather_import_material_before_hook(self, gltf_material, vertex_color, gltf):
        self("gather_import_material_before_hook", gltf_material, vertex_color, gltf)

    def gather_import_material_after_hook(
        self,
        gltf_material,
        vertex_color,
        blender_mat,
        gltf,
    ):
        self(
            "gather_import_material_after_hook",
            gltf_material,
            vertex_color,
            blender_mat,
            gltf,
        )
