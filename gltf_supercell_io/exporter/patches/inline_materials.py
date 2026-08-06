from ...com.utilities.patcher import Patch


def can_use_inline(self):
    return False

# Well.... what i can say...
# glTF IO in Blender 5.2 decided to use inlined materials for some reason, sounds like a good idea
# https://github.com/KhronosGroup/glTF-Blender-IO/blob/0bcc09ef95c1643f25023b66e53b248bf6bba508/addons/io_scene_gltf2/blender/exp/material/materials.py#L80
# But this is works so good that it completely breaks core of material system
# Since this shit inlining everything and even custom groups instantiated from library
# glTF IO devs added special check for their own custom nodes but not for other peoples custom nodes :sigarette:
inline_materials = Patch(
    "inline materials",
    module_path="io_scene_gltf2.blender.exp.material.materials",
    target_class="BlenderMaterialIndentifier",
    target_method="_BlenderMaterialIndentifier__can_use_inline",
    function=can_use_inline,
)
