import bpy
from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread
from typing import Any, cast, TYPE_CHECKING
from ...net.asset_request import AssetRequest, list_assets
from .helpers import clean_asset_browser_cache
from pathlib import Path

if TYPE_CHECKING:
    from .asset_browser import AssetBrowserProperties

_request_counter = 0


def _create_request_id():
    global _request_counter
    _request_counter += 1
    return _request_counter


@dataclass
class RefreshRequest:
    request: AssetRequest
    force: bool
    id: int = _create_request_id()


@dataclass
class RefreshResult:
    id: int
    files: list[str]


_request_queue: Queue = Queue()
_result_queue: Queue = Queue()

_worker_thread = None
_worker_running = False


def _worker_loop():
    global _worker_running

    while _worker_running:
        try:
            msg: RefreshRequest = _request_queue.get(timeout=0.25)
        except Empty:
            continue

        try:
            if msg.force:
                clean_asset_browser_cache()

            files = list_assets(msg.request)
            if files is None:
                continue

            _result_queue.put(
                RefreshResult(
                    id=msg.id,
                    files=files,
                )
            )

        except Exception as ex:
            print("Asset browser worker error:", ex)


def update_asset_browser(msg: RefreshRequest):
    try:
        while True:
            _request_queue.get_nowait()
    except Empty:
        pass

    _request_queue.put(msg)


def stop_asset_worker():
    global _worker_running
    global _worker_thread

    _worker_running = False
    if _worker_thread:
        _worker_thread.join(timeout=1.0)

    _worker_thread = None


def start_asset_worker():
    global _worker_thread
    global _worker_running

    if _worker_thread is not None:
        return

    _worker_running = True

    _worker_thread = Thread(
        target=_worker_loop,
        daemon=True,
        name="SCAssetBrowserWorker",
    )

    _worker_thread.start()


def asset_browser_timer():
    global _request_counter

    try:
        while True:
            result: RefreshResult = _result_queue.get_nowait()

            if result.id != _request_counter:
                continue

            scene = bpy.context.scene

            props = cast(
                "AssetBrowserProperties",
                cast(Any, scene).sc_asset_browser,
            )

            props.assets.clear()

            for path in result.files:
                item = props.assets.add()
                item.path = path
                item.name = Path(path).stem

    except Empty:
        pass

    return 0.2
