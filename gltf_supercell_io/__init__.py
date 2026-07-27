import bpy
from typing import cast, Any

from .com.editor.string_array import *
from .exporter.ui import glTFSupercellExporterProperties
from .importer.ui import glTFSupercellImporterProperties, glTFSupercellTextureOverride
from .com.shader.handler import shader_linkage_handler
from .com.shader.nodes import ShaderNodeScShader, ShaderNodeScUtility, ShaderNodeScNode
from .com.editor import (
    SHADER_OT_SC_create_shader,
    SHADER_PT_SC_create_shader,
    SHADER_PT_SC_create_utilities,
)
from .exporter.ui import draw_export
from .exporter import glTF2ExportUserExtension
from .importer.ui import draw_import
from .importer import glTF2ImportUserExtension
from .importer.patches import flatbuffer_glb, skinned_mesh
from .com.utilities.patcher import register_patch, unregister_patch
from .exporter.patches import inverse_bind_matrices_gather
from .com.editor.string_array import (
    StringItem,
    DirectoryStringItem,
    STRING_ARRAY_UL_items,
    STRING_ARRAY_OT_add,
    STRING_ARRAY_OT_remove,
    STRING_ARRAY_STATE,
)
from .com.editor.asset_importer import (
    ASSETS_OT_import,
    ASSETS_OT_import_api,
    ASSETS_PT_panel,
    ASSETS_OT_refresh,
    ASSETS_UL_list,
    AssetBrowserProperties,
    AssetBrowserItem,
    cleanup_temporary_files,
    refresh_handler,
    asset_browser_timer,
    start_asset_worker,
    stop_asset_worker,
)
from .preferences import SupercellGLTFPreferences

classes = [
    # String array panel
    StringItem,
    DirectoryStringItem,
    STRING_ARRAY_UL_items,
    STRING_ARRAY_OT_add,
    STRING_ARRAY_OT_remove,
    STRING_ARRAY_STATE,
    glTFSupercellTextureOverride,  # Texture override descriptor
    glTFSupercellImporterProperties,  # Importer properties
    glTFSupercellExporterProperties,  # Exporter properties
    ShaderNodeScNode,  # Base class for custom nodes
    ShaderNodeScUtility,  # Custom utility nodes holder
    ShaderNodeScShader,  # Custom shader node holder
    SHADER_PT_SC_create_shader,  # Custom shader graph panel
    SHADER_OT_SC_create_shader,  # Create shader operator
    SHADER_PT_SC_create_utilities,  # Create utility node trees
    SupercellGLTFPreferences,  # Addon preferences
    # Assets import
    ASSETS_OT_import,
    ASSETS_OT_import_api,
    ASSETS_PT_panel,
    ASSETS_OT_refresh,
    ASSETS_UL_list,
    AssetBrowserItem,
    AssetBrowserProperties,
]

patches = [flatbuffer_glb, skinned_mesh, inverse_bind_matrices_gather]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    for patch in patches:
        register_patch(patch)

    scene = cast(Any, bpy.types.Scene)
    window = cast(Any, bpy.types.WindowManager)

    scene.glTFSupercellImporterProperties = bpy.props.PointerProperty(
        type=glTFSupercellImporterProperties
    )
    scene.glTFSupercellExporterProperties = bpy.props.PointerProperty(
        type=glTFSupercellExporterProperties
    )
    window.scgltf_string_array_state = bpy.props.PointerProperty(
        type=STRING_ARRAY_STATE
    )
    scene.sc_asset_browser = bpy.props.PointerProperty(type=AssetBrowserProperties)

    start_asset_worker()

    bpy.app.handlers.load_post.append(shader_linkage_handler)
    bpy.app.handlers.load_post.append(refresh_handler)
    bpy.app.timers.register(
        asset_browser_timer,
        persistent=True,
    )

    # Use the following 2 lines to register the UI for this hook
    from io_scene_gltf2 import exporter_extension_layout_draw

    # Make sure to use the same name in unregister()
    exporter_extension_layout_draw["Supercell"] = draw_export


def unregister():
    scene = cast(Any, bpy.types.Scene)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    del scene.glTFSupercellImporterProperties
    del scene.glTFSupercellExporterProperties
    del scene.sc_asset_browser

    from io_scene_gltf2 import exporter_extension_layout_draw

    # Make sure to use the same name in register()
    if "Supercell" in exporter_extension_layout_draw:
        del exporter_extension_layout_draw["Supercell"]

    cleanup_temporary_files()
    stop_asset_worker()
    bpy.app.handlers.load_post.remove(shader_linkage_handler)
    bpy.app.handlers.load_post.remove(refresh_handler)
    bpy.app.timers.unregister(asset_browser_timer)
