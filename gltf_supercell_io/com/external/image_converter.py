import addon_utils
from importlib import import_module
from types import ModuleType

REPOSITORIES = [
    "bl_ext.vscode_development",
    "bl_ext.blender_org",
    "bl_ext.user_default",
    "bl_ext.system",
]
MODULE_NAME = "gltf_image_converter"
_candidates = [MODULE_NAME] + [".".join([repo, MODULE_NAME]) for repo in REPOSITORIES]

_loaded = False
_image_converter_name: str = ""
_image_converter: ModuleType | None = None


def load_image_converter():
    global _loaded
    global _image_converter
    global _image_converter_name

    if _loaded:
        if not addon_utils.check(_image_converter_name)[1]:
            return None

        return _image_converter

    for candidate in _candidates:
        default_import, enabled = addon_utils.check(candidate)
        print(
            f"Trying to load {candidate}: default import - {default_import}, enabled - {enabled}"
        )
        if enabled:
            print(f'Loaded external "{candidate}" module')
            _image_converter = import_module(candidate)
            _image_converter_name = candidate
            break

    _loaded = True
    return _image_converter
