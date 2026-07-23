from typing import Any, cast

from bpy.types import UILayout, Context, PropertyGroup
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from ..com.shader_presets import ShaderPresetType
from ..com import glTF_extension_name

fps_source_items = (
    (
        "SEQUENCE",
        "Sequence",
        "The sequence frame rate matches the original frame rate",
        "ACTION",
        0,
    ),
    (
        "SCENE",
        "Scene",
        "The sequence is resampled to the frame rate of the scene",
        "SCENE_DATA",
        1,
    ),
    ("CUSTOM", "Custom", "The sequence is resampled to a custom frame rate", 2),
)

materials_source_items = (
    (
        "IMPORT",
        "Import",
        "Creates new materials as usual, so even if the materials exist, new instances will be created specifically for the imported resources",
        "FILE_NEW",
        0,
    ),
    (
        "EXISTINGS",
        "Existing",
        "Attempts to use existing materials in the scene. Useful for assets that are split across multiple files but share the same material.",
        "BLENDER",
        1,
    ),
)


class glTFSupercellImporterProperties(PropertyGroup):
    single_skeleton: BoolProperty(
        name="Import as single skeleton",
        description="Imports whole scene under a single armature. Useful for characters with many parts.",
        default=True,
    )

    better_settings: BoolProperty(
        name="Custom glTF importer settings",
        description="Sets some importer settings to better values for Supercell models",
        default=True,
    )

    shader_preset: EnumProperty(
        name="Material preset",
        description="Select shader preset for imported material",
        items=[
            (str(ShaderPresetType.UNLIT), "Unlit", "Use unlit materials"),
            (
                str(ShaderPresetType.BRAWL_STARS_LEGACY),
                "Legacy Brawl Stars",
                "Use older version of Brawl Stars materials",
            ),
            (
                str(ShaderPresetType.BSDF),
                "Principled BSDF",
                "Use default Blender shader for materials. Take note that most of SC materials data will be lost.",
            ),
        ],
        default=str(ShaderPresetType.UNLIT),
    )

    adjust_colorspace: BoolProperty(
        name="Adjust color space",
        description="Configures color space required for correct display of SC shaders",
        default=True,
    )

    fps_source: EnumProperty(name="FPS Source", items=fps_source_items)
    fps_custom: FloatProperty(
        default=30.0,
        name="Custom FPS",
        description="The frame rate to which the imported sequences will be resampled to",
        options=set(),
        min=1.0,
        soft_min=1.0,
        soft_max=60.0,
        step=100,
    )

    material_source: EnumProperty(name="Material Source", items=materials_source_items)


def draw_import(context: Context, layout: UILayout):
    if not context.scene:
        return

    header, body = layout.panel(glTF_extension_name, default_closed=False)
    header.label(text="Supercell")
    header.use_property_split = False

    props = cast(
        "glTFSupercellImporterProperties",
        cast(Any, context.scene).glTFSupercellImporterProperties,
    )
    if body is None:
        return

    body.prop(props, "shader_preset")
    body.prop(props, "fps_source")
    if props.fps_source == "CUSTOM":
        body.prop(props, "fps_custom")

    body.prop(props, "single_skeleton")
    body.prop(props, "better_settings")
    body.prop(props, "adjust_colorspace")
