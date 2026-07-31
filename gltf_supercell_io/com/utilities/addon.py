import bpy


def get_addon_module_name():
    preferences = bpy.context.preferences
    if preferences is None:
        raise RuntimeError("Failed to access Blender preferences")

    for mod_name in preferences.addons.keys():
        if __package__ and __package__.startswith(mod_name):
            return mod_name

    raise RuntimeError("Failed to determine addon module name")


package_name = get_addon_module_name()
