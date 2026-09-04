import bpy
import os
from typing import Any, cast, TYPE_CHECKING, Optional
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

    @staticmethod
    def download_asset(
        filepath: str, game: Optional[str] = None, version: Optional[str] = None
    ) -> Path | None:
        """Assets import API that can be called directly with provided data

        Args:
            filepath (str): Asset path (e.g sc3d/model_geo.glb)
            game (str, optional): Game name (e.g BS). Defaults to value from Asset Browser properties.
            version (str, optional): Version name (e.g 67.677.1). Defaults to value from Asset Browser properties.

        Returns:
            Path | None: Downloaded file path in temporary folder. Returns none if downloading is failed.
        """
        props = cast(
            "AssetBrowserProperties", cast(Any, bpy.context.scene).sc_asset_browser
        )

        target_game = game if game is not None else props.game
        target_version = version if version is not None else props.version

        # Getting selected version hash
        versions = list_versions(AssetRequest(game_server=target_game))
        if versions is None:
            return None

        hash = get_version_sha(target_version)

        # Getting item and creating temp path
        output_path: Path = Path(tempdir) / hash / filepath
        if not os.path.exists(output_path):
            # Downloading file
            data = download_asset_detailed(
                AssetRequest(
                    search=filepath,
                    game_server=target_game,
                    version=target_version,
                )
            )

            if data is None:
                return None

            # Saving to temp
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as file:
                file.write(data)

        return output_path

    def execute(self, context):  # type: ignore
        props = cast(
            "AssetBrowserProperties", cast(Any, context.scene).sc_asset_browser
        )

        props.currently_importing = True
        # Getting selected version hash
        filepath = ASSETS_OT_import_api.download_asset(
            self.filepath, game=self.game, version=self.version
        )
        if filepath is None:
            self.report({"ERROR"}, "Failed to download file")
            return {"CANCELLED"}

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
            version = int(props.version.split(".")[0])
            if version >= 69:
                gltf_props.shader_preset = "ScBrawlStarsShader"
            else:
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
