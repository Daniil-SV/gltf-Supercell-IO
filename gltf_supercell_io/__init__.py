from typing import Any, cast

import bpy
from io_scene_gltf2.blender.imp import scene as gltf_scene

from .com.editor import (
    SHADER_OT_SC_create_shader,
    SHADER_PT_SC_create_shader,
    SHADER_PT_SC_create_utilities,
)
from .com.editor.asset_importer import (
    AssetBrowserItem,
    AssetBrowserProperties,
    ASSETS_OT_import,
    ASSETS_OT_import_api,
    ASSETS_OT_refresh,
    ASSETS_PT_panel,
    ASSETS_UL_list,
    asset_browser_timer,
    cleanup_temporary_files,
    refresh_handler,
    start_asset_worker,
    stop_asset_worker,
)
from .com.editor.string_array import (
    STRING_ARRAY_STATE,
    DirectoryStringItem,
    STRING_ARRAY_OT_add,
    STRING_ARRAY_OT_remove,
    STRING_ARRAY_UL_items,
    StringItem,
)
from .com.shader.handler import shader_linkage_handler
from .com.shader.nodes import ShaderNodeScNode, ShaderNodeScShader, ShaderNodeScUtility
from .com.utilities.patcher import register_patch, unregister_patch
from .exporter import glTF2ExportUserExtension as glTF2ExportUserExtension
from .exporter.patches import (
    buffer_caching_patch,
    fcurve_keyframes_patch,
    flat_glb_output,
    inline_materials,
    inverse_bind_matrices_gather,
    primitive_gather_attribute,
    primitive_master_hook,
    sampled_armature_keyframes_patch,
    traverse_gather,
)
from .exporter.ui import draw_export, glTFSupercellExporterProperties
from .importer import glTF2ImportUserExtension as glTF2ImportUserExtension
from .importer.patches import flatbuffer_glb, vnodes_compute_patch
from .importer.scw.operator import ImportSCW, IO_FH_scw, scw_func_import
from .importer.ui import draw_import as draw_import
from .importer.ui import glTFSupercellImporterProperties, glTFSupercellTextureOverride
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
    ImportSCW,
    IO_FH_scw,
]

patches = [
    flatbuffer_glb,
    vnodes_compute_patch,
    inverse_bind_matrices_gather,
    traverse_gather,
    sampled_armature_keyframes_patch,
    fcurve_keyframes_patch,
    primitive_gather_attribute,
    flat_glb_output,
    primitive_master_hook,
    buffer_caching_patch,
]
patches_5_2_up = [inline_materials]


def register():
    major, minor, _build = bpy.app.version
    for cls in classes:
        bpy.utils.register_class(cls)

    for patch in patches:
        register_patch(patch)

    gltf_scene.compute_vnodes = (  # ty: ignore[invalid-assignment]
        vnodes_compute_patch.function
    )

    if major >= 5 and minor >= 2:
        for patch in patches_5_2_up:
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

    bpy.types.TOPBAR_MT_file_import.append(
        scw_func_import  # ty: ignore[invalid-argument-type]
    )

    # Use the following 2 lines to register the UI for this hook
    from io_scene_gltf2 import exporter_extension_layout_draw

    # Make sure to use the same name in unregister()
    exporter_extension_layout_draw["Supercell"] = draw_export


def unregister():
    scene = cast(Any, bpy.types.Scene)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    for patch in patches:
        unregister_patch(patch)

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

    bpy.types.TOPBAR_MT_file_import.remove(
        scw_func_import  # ty: ignore[invalid-argument-type]
    )
