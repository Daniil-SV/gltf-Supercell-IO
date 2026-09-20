import shutil
import tempfile
from typing import TYPE_CHECKING, Any, cast

import bpy
from bpy.app.handlers import persistent

from ...net.asset_request import (
    AssetRequest,
    clean_asset_fetch_cache,
    list_servers,
    list_versions,
)

if TYPE_CHECKING:
    from .asset_browser import AssetBrowserProperties

tempdir = tempfile.mkdtemp(prefix="sc-gltf-io-browser")


def get_version_items(self, context):
    props = context.scene.sc_asset_browser
    if not props.game:
        return []

    request = AssetRequest(
        game_server=props.game,
    )

    items = []
    versions = list_versions(request)
    if versions is None:
        return items

    for i, data in enumerate(versions):
        version = data["version"]
        items.append(
            (
                version,
                version,
                "",
                i,
            )
        )

    return items


def get_game_items(self, context):
    items = []
    games = list_servers()
    if games is None:
        return items

    for i, server in enumerate(games):
        items.append(
            (
                server.codename,
                server.name,
                "",
                i,
            )
        )

    return items


def get_version_sha(target_version: str) -> str:
    props = cast(
        "AssetBrowserProperties", cast(Any, bpy.context.scene).sc_asset_browser
    )
    versions = list_versions(AssetRequest(game_server=props.game))
    if versions is None:
        return "fallback"

    return next(
        (
            version["hash"]
            for version in versions
            if version["version"] == target_version
        ),
        "fallback",
    )


def cleanup_temporary_files():
    shutil.rmtree(tempdir, ignore_errors=True)


def clean_asset_browser_cache():
    clean_asset_fetch_cache()
    cleanup_temporary_files()


@persistent
def refresh_handler(dummy):
    bpy.ops.supercell.assets_refresh()  # type: ignore
