from pathlib import Path
from .component import glTF2BaseImporterComponent, requires_extension
from ...com import glTF_material_extension_name, glTF_extension_name
from ...com.materials import ScShaderMaterial
from ...com.shader_presets import ShaderPresets
from ...com.shader.importer import ShaderImporter
from ...com.editor.asset_importer import ASSETS_OT_import_api
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from ..scw import ScwFile


class SupercellShaderImporter(glTF2BaseImporterComponent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.material_override: list[dict] = []

    def load_material_file(self, filepath: Path, import_settings: dict):
        if filepath.suffix == ".scw":
            scw = ScwFile(str(filepath), import_settings)
            scw.read()

            return scw.gltf
        else:
            importer = glTFImporter(str(filepath), import_settings)
            importer.read()

            return importer

    @requires_extension
    def gather_import_gltf_before_hook(self, gltf):
        if not self.properties.material_override:
            return

        base_dir = Path(gltf.import_settings["directory"])
        materials_path = Path(self.properties.material_override)
        candidates = [
            materials_path,
            base_dir / materials_path,
            base_dir / materials_path.name,
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

        gltf = self.load_material_file(filepath, {"import_user_extensions": []})

        # Gathering usual materials
        for material in gltf.data.materials or []:
            if glTF_material_extension_name not in material.extensions or {}:
                continue

            self.material_override.append(
                material.extensions[glTF_material_extension_name]
            )

        # Gathering odin materials
        if glTF_extension_name in gltf.data.extensions or {}:
            odin: dict = gltf.data.extensions[glTF_extension_name]
            for material in odin.get("materials", []):
                self.material_override.append(material)

    @requires_extension
    def gather_import_material_before_hook(
        self, gltf_material, vertex_color: str, gltf
    ):
        extensions = gltf_material.extensions = gltf_material.extensions or {}
        descriptor: dict | None = extensions.get(glTF_material_extension_name)  # type: ignore
        material_name: str | None = (
            gltf_material.name if descriptor is None else descriptor.get("name")
        )

        if material_name is not None:
            override = self.try_find_override(material_name)
            if override is not None:
                descriptor = override

        if descriptor is None or isinstance(descriptor, ScShaderMaterial):
            return

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

        if self.properties.shader_preset == "None":
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
