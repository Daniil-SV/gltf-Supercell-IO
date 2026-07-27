import sys
from dataclasses import dataclass
from typing import Any, Callable
import types
import importlib


@dataclass
class Patch:
    name: str
    target_method: str
    module_path: str
    function: Callable
    target_class: str | None = None


_PATCH_REGISTRY: dict[str, tuple[Any, str, Any]] = {}


def register_patch(patch: Patch) -> None:
    try:
        if patch.module_path in sys.modules:
            mod = sys.modules[patch.module_path]
        else:
            try:
                mod = importlib.import_module(patch.module_path)
            except ImportError:
                mod = types.ModuleType(patch.module_path)
                sys.modules[patch.module_path] = mod

        if patch.target_class is not None:
            target_obj = getattr(mod, patch.target_class)
        else:
            target_obj = mod

        if patch.name in _PATCH_REGISTRY:
            return

        original_value = getattr(target_obj, patch.target_method, None)
        _PATCH_REGISTRY[patch.name] = (target_obj, patch.target_method, original_value)

        setattr(target_obj, patch.target_method, patch.function)
        print(f"[SC IO] Successfully patched: {patch.name}")

    except Exception as e:
        print(f"[SC IO] Failed to patch {patch.name}: {e}")


def unregister_patch(patch: Patch) -> None:
    if patch.name not in _PATCH_REGISTRY:
        print(f"[SC IO] Patch '{patch.name}' is not registered.")
        return

    target_obj, target_method, original_value = _PATCH_REGISTRY.pop(patch.name)

    try:
        if original_value is None:
            if hasattr(target_obj, target_method):
                delattr(target_obj, target_method)
        else:
            setattr(target_obj, target_method, original_value)

        print(f"[SC IO] Successfully unpatched: {patch.name}")

    except Exception as e:
        print(f"[SC IO] Failed to unpatch {patch.name}: {e}")
