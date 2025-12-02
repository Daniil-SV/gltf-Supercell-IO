import bpy
from bpy.types import UILayout, Context
from bpy.props import BoolProperty, FloatProperty
from ..com import glTF_extension_name


class glTFSupercellImporterProperties(bpy.types.PropertyGroup):
    single_skeleton: BoolProperty(
        description='Imports whole scene under a single armature. Useful for characters with many parts.',
        default=True
    )
    
    better_settings: BoolProperty(
        description='Sets some importer settings to better values for Supercell models',
        default=True
    )

def draw_import(context: Context, layout: UILayout):
    header, body = layout.panel(glTF_extension_name, default_closed=False)
    header.label(text="Supercell")
    header.use_property_split = False

    props = bpy.context.scene.glTFSupercellImporterProperties
    if body != None:
        body.prop(props, 'single_skeleton', text="Import as single skeleton")
