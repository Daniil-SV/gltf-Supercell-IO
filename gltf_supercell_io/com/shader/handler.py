from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from .loader import LibraryLoader


@persistent
def shader_linkage_handler(dummy):
    for lib in bpy.data.libraries:
        path = Path(lib.filepath)
        if path.name == LibraryLoader.LibraryName and not path.exists():
            lib.filepath = str(LibraryLoader.LibraryPath)
            lib.reload()
