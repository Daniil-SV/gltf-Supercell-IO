import bpy

from .helpers import get_game_items, get_version_items
from .operator import ASSETS_OT_refresh


class AssetBrowserItem(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty()
    name: bpy.props.StringProperty()


class AssetBrowserProperties(bpy.types.PropertyGroup):
    search: bpy.props.StringProperty(
        name="Search",
        default="",
        update=lambda _self, ctx: ASSETS_OT_refresh.safe_refresh(ctx),
    )

    game: bpy.props.EnumProperty(
        name="Game",
        items=get_game_items,
        update=lambda _self, ctx: ASSETS_OT_refresh.safe_refresh(ctx),
    )

    version: bpy.props.EnumProperty(
        name="Version",
        items=get_version_items,
        update=lambda _self, ctx: ASSETS_OT_refresh.safe_refresh(ctx),
    )

    assets: bpy.props.CollectionProperty(type=AssetBrowserItem)
    asset_index: bpy.props.IntProperty(default=0)

    currently_importing: bpy.props.BoolProperty(default=False)
