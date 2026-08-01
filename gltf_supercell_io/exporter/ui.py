import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty
from ..com import glTF_extension_name


class glTFSupercellExporterProperties(PropertyGroup):
    enabled: BoolProperty(
        name="Supercell",
        description="Include this extension in the exported glTF file.",
        default=True,
    )

    use_odin: BoolProperty(
        name="Odin optimizations",
        description="Use Odin optimizations for meshes and animations",
        default=False,
    )

    path_prefix: StringProperty(
        name="Texture prefix",
        description="Exports textures with this prefix if needed",
        default="sc3d/",
    )

    legacy_meshes: BoolProperty(
        name="Legacy meshes",
        description="Exports mesh data in legacy format",
        default=False,
    )

    legacy_materials: BoolProperty(
        name="Legacy materials",
        description="Exports materials in legacy format",
        default=True,
    )


def draw_export(context: bpy.context, layout: bpy.types.UILayout):
    if bpy.context.scene is None:
        return

    props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore

    header, body = layout.panel(glTF_extension_name, default_closed=False)
    header.use_property_split = False
    header.prop(props, "enabled")
    if body:
        # TODO: implement odin extension and return back this option
        # For now always export materials in legacy format
        body.prop(props, "path_prefix")
        # body.prop(props, "use_odin")

    # if (body and not props.use_odin):
    if body:
        legacy_header, legacy_body = body.panel("Legacy", default_closed=True)
        legacy_header.label(text="Legacy")
        if legacy_body:
            legacy_body.prop(props, "legacy_meshes")
            legacy_body.prop(props, "legacy_materials")
