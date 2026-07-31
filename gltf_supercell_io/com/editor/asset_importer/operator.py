import bpy
import os
from typing import Any, cast, TYPE_CHECKING
from .helpers import get_version_sha, tempdir
from .worker import RefreshRequest, update_asset_browser
from ...net.asset_request import (
    AssetRequest,
    download_asset_detailed,
    list_versions,
)
from pathlib import Path

if TYPE_CHECKING:
    from .asset_browser import AssetBrowserProperties, AssetBrowserItem
    from ....importer.ui import glTFSupercellImporterProperties


class ASSETS_UL_list(bpy.types.UIList):
    def draw_item(  # type: ignore
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        layout.label(text=item.name, icon="FILE")


class ASSETS_OT_refresh(bpy.types.Operator):
    bl_idname = "supercell.assets_refresh"
    bl_label = "Refresh"

    force: bpy.props.BoolProperty(default=True)

    @staticmethod
    def safe_refresh(context):
        try:
            bpy.ops.supercell.assets_refresh(force=False)  # type: ignore
        except Exception:
            pass

    def execute(self, context):  # type: ignore
        props = cast(
            "AssetBrowserProperties",
            cast(Any, context.scene).sc_asset_browser,
        )

        request = AssetRequest(
            search=f"{props.search} .glb$",
            game_server=props.game,
            version=props.version if props.version else None,
        )

        update_asset_browser(
            RefreshRequest(
                request=request,
                force=self.force,
            )
        )

        return {"FINISHED"}


class ASSETS_OT_import_api(bpy.types.Operator):
    bl_idname = "supercell.assets_import_api"
    bl_label = "Import GLB"

    game: bpy.props.StringProperty()
    version: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty()

    def execute(self, context):  # type: ignore
        props = cast(
            "AssetBrowserProperties", cast(Any, context.scene).sc_asset_browser
        )

        props.currently_importing = True
        # Getting selected version hash
        versions = list_versions(AssetRequest(game_server=self.game))
        if versions is None:
            self.report({"ERROR"}, "Failed to fetch versions")
            return {"CANCELLED"}

        hash = get_version_sha(self.version)

        # Getting item and creating temp path
        filepath: Path = Path(tempdir) / hash / self.filepath
        if not os.path.exists(filepath):
            # Downloading file
            data = download_asset_detailed(
                AssetRequest(
                    search=self.filepath, game_server=self.game, version=self.version
                )
            )
            if data is None:
                self.report({"ERROR"}, "Failed to download file")
                return {"CANCELLED"}

            # Saving to temp
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as file:
                file.write(data)

        bpy.ops.import_scene.gltf(filepath=str(filepath))
        props.currently_importing = False
        return {"FINISHED"}


class ASSETS_OT_import(bpy.types.Operator):
    bl_idname = "supercell.assets_import"
    bl_label = "Import GLB"

    def execute(self, context):  # type: ignore
        props = cast(
            "AssetBrowserProperties", cast(Any, context.scene).sc_asset_browser
        )
        if not props.assets or not props.game or props.asset_index >= len(props.assets):
            return {"CANCELLED"}

        gltf_props = cast(
            "glTFSupercellImporterProperties",
            cast(Any, context.scene).glTFSupercellImporterProperties,
        )

        if props.game == "BS" or props.game == "BSCN":
            gltf_props.shader_preset = "ScLegacyBrawlStarsShader"

        item = cast("AssetBrowserItem", props.assets[props.asset_index])
        bpy.ops.supercell.assets_import_api(  # type: ignore
            game=props.game, version=props.version, filepath=item.path
        )

        return {"FINISHED"}


class ASSETS_PT_panel(bpy.types.Panel):
    bl_label = "Asset Browser"
    bl_idname = "ASSETS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Supercell"
    
    @classmethod
    def poll(cls, context) -> bool:
        # Render only when has access to internet
        return bpy.app.online_access

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = cast(
            "AssetBrowserProperties", cast(Any, context.scene).sc_asset_browser
        )

        if layout is None or scene is None:
            return

        # Top bar
        row = layout.row(align=True)
        row.prop(props, "search", text="", icon="VIEWZOOM")
        row.operator("supercell.assets_refresh", text="", icon="FILE_REFRESH")

        # Filters
        layout.prop(props, "game")
        layout.prop(props, "version")

        # Assets list
        layout.separator()
        layout.template_list(
            "ASSETS_UL_list",
            "",
            props,
            "assets",
            props,
            "asset_index",
            rows=10,
        )

        # Import button
        layout.operator(
            "supercell.assets_import",
            text="Import Selected",
            icon="IMPORT",
        )
