# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import bpy

bl_info = {
    "name": "glTF Supercell IO",
    "author": "DaniilSV",
    "description": "",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}

from .importer.ui import glTFSupercellImporterProperties
from .importer.importer_patch import patch_importer

# Initialization functions for glTF importer extension
from .importer.ui import draw_import
from .importer import glTF2ImportUserExtension

def register():
    bpy.utils.register_class(glTFSupercellImporterProperties)
    bpy.types.Scene.glTFSupercellImporterProperties = bpy.props.PointerProperty(type=glTFSupercellImporterProperties)
    patch_importer()

def unregister():
    bpy.utils.unregister_class(glTFSupercellImporterProperties)
    del bpy.types.Scene.glTFSupercellImporterProperties
