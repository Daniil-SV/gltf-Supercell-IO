from typing import TYPE_CHECKING, Any, cast

import bpy
import tempfile
import hashlib
import os
from pathlib import Path
from io import BytesIO

from ..editor.asset_importer.helpers import get_version_sha
from .asset_request import AssetRequest, download_asset_detailed
from neko_web_api_client import Client
from neko_web_api_client.api.assets import post_v1_texture_png
from neko_web_api_client.api.default import post_v1_cdn
from neko_web_api_client.models import (
    AssetsReferenceResponse,
    ErrorResponse,
    ImageConverterLoaders,
    AssetsInputBody,
    AssetDescribeType,
)
from neko_web_api_client.types import File
from functools import lru_cache

if TYPE_CHECKING:
    from ..editor.asset_importer import AssetBrowserProperties

tempdir = os.path.join(tempfile.gettempdir(), "sc-gltf-io-textures")

client = Client(base_url="https://api.sc-workshop.com")


def _fetch_texture_data(low: str, high: str) -> bytes | None:
    global client
    if not bpy.app.online_access:
        return None

    response = post_v1_cdn.sync(client=client, high=high, low=low)

    if isinstance(response, ErrorResponse):
        print(f"Failed to download texture from cdn: {response.message}")

    if isinstance(response, File):
        return response.payload.read()

    return None


def _handle_response(
    response: AssetsReferenceResponse | ErrorResponse | None, cache_path: str
) -> bytes | None:
    if response is None:
        print("Request to post_v1_texture_png_files is failed")
        return None

    if isinstance(response, AssetsReferenceResponse):
        result = _fetch_texture_data(response.low, response.high)
        if result is not None:
            with open(cache_path, "wb") as f:
                f.write(result)
        return result

    print(f"Failed to convert texture: {response.message}")
    return None


@lru_cache(maxsize=5)
def _convert_texture_cached(name: str, game: str, version: str) -> bytes | None:
    global client

    hash = get_version_sha(version)
    temp_texture_path = os.path.join(tempdir, hash, name + ".png")
    os.makedirs(os.path.dirname(temp_texture_path), exist_ok=True)
    try:
        if os.path.isfile(temp_texture_path):
            with open(temp_texture_path, "rb") as file:
                return file.read()
    except Exception as e:
        print(f'Failed to read texture cache at "{temp_texture_path}"\n{e}')

    path = Path(name)
    search = f"{path.stem}|{path.suffix}$"
    request = AssetRequest(search, game_server=game, version=version)

    response = post_v1_texture_png.sync(
        client=client,
        request=str(request),
        request_type=AssetDescribeType.DATABASE,
        source=ImageConverterLoaders.AUTO,
    )

    return _handle_response(response, temp_texture_path)


def download_raw_texture(name: str) -> tuple[str, bytes] | None:
    props = cast(
        "AssetBrowserProperties", cast(Any, bpy.context.scene).sc_asset_browser
    )

    hash = get_version_sha(props.version)
    temp_texture_path = os.path.join(tempdir, hash, name)
    os.makedirs(os.path.dirname(temp_texture_path), exist_ok=True)

    try:
        if os.path.isfile(temp_texture_path):
            with open(temp_texture_path, "rb") as file:
                return (temp_texture_path, file.read())

    except Exception as e:
        print(f'Failed to read texture cache at "{temp_texture_path}"\n{e}')

    request = AssetRequest(name, game_server=props.game, version=props.version)
    result = download_asset_detailed(request)
    if result is not None:
        with open(temp_texture_path, "wb") as f:
            f.write(result)

    if result is not None:
        return (temp_texture_path, result)

    return None


def convert_texture(name: str) -> bytes | None:
    props = cast(
        "AssetBrowserProperties", cast(Any, bpy.context.scene).sc_asset_browser
    )
    if not props.currently_importing:
        return None

    return _convert_texture_cached(name, props.game, props.version)


@lru_cache(maxsize=5)
def convert_user_texture(name: str, buffer: bytes) -> bytes | None:
    global client
    texture_hash = hashlib.md5(buffer)
    temp_texture_path = os.path.join(tempdir, texture_hash.hexdigest())

    try:
        if os.path.isfile(temp_texture_path):
            with open(temp_texture_path, "rb") as file:
                return file.read()

    except Exception as e:
        print(f'Failed to read texture cache at "{temp_texture_path}"\n{e}')

    body = AssetsInputBody(
        [
            File(
                BytesIO(buffer),
                name,
            )
        ]
    )

    response = post_v1_texture_png.sync(
        client=client,
        body=body,
        request_type=AssetDescribeType.USER_FILES,
        source=ImageConverterLoaders.AUTO,
    )

    return _handle_response(response, temp_texture_path)
