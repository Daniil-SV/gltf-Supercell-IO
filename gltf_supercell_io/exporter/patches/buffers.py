from io_scene_gltf2.io.exp.buffer import Buffer

from ...com.utilities.patcher import Patch

__cache: dict = {}

original = Buffer.add_and_get_view


def add_and_get_view(*args, **kwargs):
    key = (args[1:], *kwargs.values())
    if key in __cache:
        return __cache[key]

    result = __cache[key] = original(*args, **kwargs)
    return result


def clear_buffer_cache():
    __cache.clear()


# For some reason, the gltf2 io doesn't perform any buffer caching,
# so the same data, which can be used by multiple objects,
# is written multiple times instead of just once.
# I believe this is because the gltf2 io uses its own buffer for all data,
# but even so, it's a strange implementation.
# This is especially critical for Odin, which stores everything in a
# single buffer and to which almost all objects are referenced, and the current implementation
# causes the buffer to bloat dozens of times.
# This is a very simple but effective patch, so I think that there is no need to add a
# separate check for Odin, so this will work for exporting all glb's.
buffer_caching_patch = Patch(
    "buffer caching",
    module_path="io_scene_gltf2.io.exp.buffer",
    target_class="Buffer",
    target_method="add_and_get_view",
    function=add_and_get_view,
)
