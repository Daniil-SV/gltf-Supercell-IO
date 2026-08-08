import bpy
from bpy.types import AddonPreferences
from bpy.props import CollectionProperty
from .com.editor.string_array import DirectoryStringItem, StringArray
from typing import cast


def get_package_name():
    return __package__ or "gltf_supercell_io"


class SupercellGLTFPreferences(AddonPreferences):
    # This must match the add-on name, use `__package__`
    # when defining this for add-on extensions or a sub-module of a Python package.
    bl_idname = get_package_name()

    texture_lookup: CollectionProperty(type=DirectoryStringItem, name="Paths")

    def draw(self, context):
        layout = self.layout
        StringArray.draw(
            layout=layout,
            data_path=f'preferences.addons["{get_package_name()}"].preferences',
            collection_prop="texture_lookup",
            label="Lookup textures",
            default_value="",
        )


def get_prefs() -> SupercellGLTFPreferences | None:
    prefs = bpy.context.preferences
    if prefs is None:
        return None

    addon = prefs.addons[get_package_name()]
    if addon is None or addon.preferences is None:
        return None

    return cast(SupercellGLTFPreferences, addon.preferences)
