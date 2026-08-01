from pathlib import Path
from .component import glTF2BaseImporterComponent, requires_extension
from ...com import glTF_material_extension_name, glTF_extension_name
from ...com.materials import ScShaderMaterial
from ...com.shader_presets import ShaderPresets
from ...com.shader.importer import ShaderImporter
from ...com.editor.asset_importer import ASSETS_OT_import_api
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter


class SupercellShaderImporter(glTF2BaseImporterComponent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.material_override: list[dict] = []

    @requires_extension
    def gather_import_gltf_before_hook(self, gltf):
        if not self.properties.material_override:
            return

        candidates: list[Path] = [
            Path(self.properties.material_override),
            Path(gltf.import_settings["directory"])
            / self.properties.material_override,  # Trying with glb directory as base directory
        ]

        filepath = None
        for candidate in candidates:
            if candidate.is_file():
                filepath = candidate
                break

        # Trying to import from asset browser
        if filepath is None:
            filepath = ASSETS_OT_import_api.download_asset(
                self.properties.material_override
            )

        if filepath is None:
            return

        importer = glTFImporter(filepath, {"import_user_extensions": []})
        importer.read()

        # Gathering usual materials
        for material in importer.data.materials or []:
            if glTF_material_extension_name not in material.extensions or {}:
                continue

            self.material_override.append(
                material.extensions[glTF_material_extension_name]
            )

        # Gathering odin materials
        if glTF_extension_name in importer.data.extensions:
            odin: dict = importer.data.extensions[glTF_extension_name]
            for material in odin.get("materials", []):
                self.material_override.append(material)

    @requires_extension
    def gather_import_material_before_hook(
        self, gltf_material, vertex_color: str, gltf
    ):
        extensions = gltf_material.extensions = gltf_material.extensions or {}
        descriptor: dict | None = extensions.get(glTF_material_extension_name)  # type: ignore
        if descriptor is None:
            return

        material_name: str | None = descriptor.get("name")
        if material_name is not None:
            override = self.try_find_override(material_name)
            if override is not None:
                descriptor = override

        material = descriptor
        if not isinstance(material, ScShaderMaterial):
            material = ScShaderMaterial()
            material.from_dict(gltf, descriptor)
            extensions[glTF_material_extension_name] = material

        gltf_material.name = material.name

    def try_find_override(self, name: str) -> dict | None:
        for material in self.material_override:
            material_name = material.get("name")

            if material_name == name:
                return material

        return None

    @requires_extension
    def gather_import_material_after_hook(
        self,
        gltf_material,
        vertex_color,
        blender_mat,
        gltf,
    ):
        extensions = gltf_material.extensions or {}
        material = extensions.get(glTF_material_extension_name)
        if material is None:
            return

        # Cleanup material from glTF fallback and prepare for our own processing
        gltf_material.pbr_metallic_roughness.blender_nodetree = None
        gltf_material.pbr_metallic_roughness.blender_mat = None
        if not blender_mat.node_tree:
            blender_mat.use_nodes = True

        tree = blender_mat.node_tree
        if tree is None:
            return
        tree.nodes.clear()

        preset = ShaderPresets.get_preset_by_id(self.properties.shader_preset)
        importer = ShaderImporter(gltf, material, blender_mat, preset)
        importer.import_material()
