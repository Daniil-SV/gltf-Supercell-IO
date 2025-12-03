import bpy
from bpy.types import UILayout, Context, PropertyGroup
from bpy.props import BoolProperty, EnumProperty
from ..com.shader.builder import ShaderPresetType
from ..com import glTF_extension_name


class glTFSupercellImporterProperties(PropertyGroup):
    single_skeleton: BoolProperty(
        description='Imports whole scene under a single armature. Useful for characters with many parts.',
        default=True
    )
    
    better_settings: BoolProperty(
        description='Sets some importer settings to better values for Supercell models',
        default=True
    )
    
    shader_preset: EnumProperty(
        name="Shader Preset",
        description="Select shader preset for imported material",
        items=[
            (str(ShaderPresetType.UNLIT), "Unlit", "Use unlit materials"),
            (str(ShaderPresetType.BRAWL_STARS_LEGACY), "Legacy Brawl Stars", "Use older version of Brawl Stars materials"),
        ],
        default=str(ShaderPresetType.UNLIT)
    )
    
    adjust_colorspace: BoolProperty(
        description='Configures color space required for correct display of SC shaders',
        default=True
    )

def draw_import(context: Context, layout: UILayout):
    header, body = layout.panel(glTF_extension_name, default_closed=False)
    header.label(text="Supercell")
    header.use_property_split = False

    props = bpy.context.scene.glTFSupercellImporterProperties
    if body != None:
        body.prop(props, 'shader_preset', text="Material preset")
        body.prop(props, 'single_skeleton', text="Import as single skeleton")
        body.prop(props, 'better_settings', text="Use custom glTF importer settings")
        body.prop(props, 'adjust_colorspace', text="Adjust color space")
