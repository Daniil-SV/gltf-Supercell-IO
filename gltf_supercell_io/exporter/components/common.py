import bpy
from mathutils import Vector, Matrix
from .component import glTF2BaseExporterComponent
from ...com import glTF_material_extension_name, glTF_extension_name
from io_scene_gltf2.blender.exp.tree import VExportNode
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension


class CommonExporter(glTF2BaseExporterComponent):
    def gather_gltf_extensions_hook(self, gltf, export_settings):
        extension = {}
        if not self.properties.legacy_materials:
            materials = export_settings[glTF_material_extension_name]
            if len(materials):
                extension["materials"] = materials
                gltf.materials = []

        if extension:
            gltf.extensions[glTF_extension_name] = Extension(
                glTF_extension_name, extension, True
            )

        gltf.asset.generator += " | Supercell-IO Exporter by DaniilSV"

    def pre_export_hook(self, export_settings: dict):
        if not self.properties.legacy_materials:
            export_settings[glTF_material_extension_name] = []

    def vtree_before_filter_hook(self, vtree, export_settings):
        # Handle node scale override
        for key in vtree.nodes.keys():
            vnode: VExportNode = vtree.nodes[key]
            if vnode.blender_type != VExportNode.BONE or vnode.blender_bone is None:
                continue

            bone: bpy.types.PoseBone = vnode.blender_bone
            scale = bone.get("scScaleOverride", None)
            if scale is None:
                continue

            x, y, z = (value for value in scale)
            matrix = vnode.matrix_world if vnode.matrix_world else Matrix.Identity(4)
            t, r, s = matrix.decompose()
            s = scale = Vector((s.x * x, s.y * y, s.z * z))

            vnode.matrix_world = (  # type: ignore
                Matrix.Translation(t)
                @ r.to_matrix().to_4x4()
                @ Matrix.Diagonal((*s, 1.0))
            )
