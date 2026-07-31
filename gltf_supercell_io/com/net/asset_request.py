import bpy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
import requests

ASSETS_ENDPOINT_URL = "https://files.sc-workshop.com/asset-request/"
SERVERS_ENDPOINT_URL = "https://files.sc-workshop.com/servers/"
TIMEOUT = 5  # seconds


class AssetRequestType(StrEnum):
    Download = "downloadAssets"
    List = "listAssets"
    ListVersions = "listVersions"
    ListServers = "listServers"


@dataclass
class Server:
    name: str
    codename: str


@dataclass
class Version:
    version: str
    hash: str


@dataclass
class AssetRequest:
    search: str = ""
    game_server: str = "BS"
    version: str | None = None
    count: int | None = None
    page: int | None = None

    @property
    def request(self) -> str:
        request = []
        request.append(
            "|".join([string for string in self.search.split(" ") if string])
        )

        request.append(self.game_server)
        if self.version:
            request.append(f"v{self.version}")

        return " ".join(request)

    @property
    def params(self):
        params: dict[str, Any] = {"request": self.request, "compressed": "false"}

        if self.count is not None:
            params["size"] = self.count

        if self.page is not None:
            params["index"] = self.page

        return params

    def __str__(self):
        return self.request

    def __eq__(self, other):
        if isinstance(other, AssetRequest):
            return (
                self.request == other.request
                and self.count == other.count
                and self.page == other.page
            )
        return False

    def __hash__(self):
        key = self.request
        if self.count is not None:
            key += f" count:{self.count}"

        if self.page is not None:
            key += f" page:{self.page}"

        return hash(key)


_cached_versions: dict[AssetRequest, list[dict] | None] = {}
_cached_assets: dict[AssetRequest, list[str] | None] = {}
_cached_servers: list[Server] | None = None


def list_assets(data: AssetRequest) -> list[str] | None:
    global _cached_assets
    if not bpy.app.online_access:
        return None

    cached = _cached_assets.get(data)
    if cached is not None:
        return cached

    result = []
    params: dict[str, Any] = {"type": AssetRequestType.List.value} | data.params

    try:
        response = requests.get(ASSETS_ENDPOINT_URL, params, timeout=TIMEOUT)
        if response.status_code == 200:
            result = response.json()
        else:
            print(
                f"Failed to fetch assets list from {ASSETS_ENDPOINT_URL}: {response.status_code} - {response.text}"
            )
    except Exception as e:
        print(f"Failed to fetch assets list from {ASSETS_ENDPOINT_URL}\n{e}")

    _cached_assets[data] = result
    return result


def list_versions(data: AssetRequest) -> list[dict] | None:
    global _cached_versions
    if not bpy.app.online_access:
        return None

    cached = _cached_versions.get(data)
    if cached is not None:
        return cached

    result = []
    params: dict[str, Any] = {"type": AssetRequestType.ListVersions.value} | data.params

    try:
        response = requests.get(ASSETS_ENDPOINT_URL, params, timeout=TIMEOUT)
        if response.status_code == 200:
            result = response.json()
        else:
            print(
                f"Failed to fetch version from {ASSETS_ENDPOINT_URL}: {response.status_code} - {response.text}"
            )
            return None
    except Exception as e:
        print(f"Failed to fetch version from {ASSETS_ENDPOINT_URL}\n{e}")

    _cached_versions[data] = result
    return result


def list_servers() -> list[Server] | None:
    global _cached_servers
    if not bpy.app.online_access:
        return None

    if _cached_servers is not None:
        return _cached_servers

    result: list[dict] = []

    try:
        response = requests.get(SERVERS_ENDPOINT_URL, timeout=TIMEOUT)

        if response.status_code == 200:
            result = response.json()
        else:
            print(
                f"Failed to fetch servers from {SERVERS_ENDPOINT_URL}: {response.status_code} - {response.text}"
            )
    except Exception as e:
        print(f"Failed to fetch servers from {SERVERS_ENDPOINT_URL}\n{e}")

    _cached_servers = [Server(**server) for server in result]
    return _cached_servers


def download_asset_detailed(request: AssetRequest) -> bytes | None:
    if not bpy.app.online_access:
        return None

    request.count = 1
    request.page = 0
    result = requests.get(
        ASSETS_ENDPOINT_URL,
        params={"type": AssetRequestType.Download.value} | request.params,
        timeout=TIMEOUT,
    )

    if result.status_code == 200:
        return result.content

    return None


def download_asset(request: str) -> bytes | None:
    servers = list_servers()
    if servers is None:
        return None

    result = None
    for game in servers:
        result = download_asset_detailed(
            AssetRequest(search=request, game_server=game.codename)
        )
        if result is not None:
            break

    return result


def clean_asset_fetch_cache():
    global _cached_assets
    global _cached_versions
    global _cached_servers

    _cached_assets.clear()
    _cached_versions.clear()
    _cached_servers = None
