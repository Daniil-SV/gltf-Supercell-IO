from __future__ import annotations
import bpy
import numpy as np
from pathlib import Path
from os.path import join, exists
from bpy.types import (
    Node,
    NodeSocket,
    ShaderNodeTexImage,
    ShaderNodeOutputMaterial,
    Image,
    Material,
    ShaderNodeTree,
)
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.com.gltf2_io import Image as glImage
from typing import Callable, Optional, Tuple, Dict
from ..materials import ScShaderMaterial, ScBlendMode
from ..materials.variables import (
    ShaderFloatVectorProperty,
    ShaderFloatProperty,
    ShaderTextureProperty,
    ShaderBooleanProperty,
    ShaderProperty,
)
from ..utilities import ShaderUtils
from .loader import LibraryLoader
from ...preferences import get_prefs
from ..net import texture_loader
from typing import TYPE_CHECKING, Type
from ..external.image_converter import load_image_converter

if TYPE_CHECKING:
    from ..shader_presets import ShaderPresetDescriptor

# An array of image extensions that can be loaded by blender
NATIVE_IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".tga",
    ".bmp",
    ".exr",
    ".dpx",
    ".cin",
    ".hdr",
]

# An array of compressed GPU textures supported by Titan but not supported by Blender
COMPRESSED_TITAN_IMAGE_EXTENSIONS = [".sctx", ".ktx", ".pvr"]

# An array of texture extensions supported by neko api
SUPPORTED_NEKO_EXTENSIONS = [".sctx"]

# An array of all valid texture extensions
IMAGE_EXTENSIONS = NATIVE_IMAGE_EXTENSIONS + COMPRESSED_TITAN_IMAGE_EXTENSIONS

# An array of image extensions that can be loaded by Blender and supported by Titan
NATIVE_TITAN_IMAGE_EXTENSION = [".png"] + COMPRESSED_TITAN_IMAGE_EXTENSIONS

NATIVE_NODES = [
    cls
    for cls in dir(bpy.types)
    if isinstance(getattr(bpy.types, cls), type)
    and issubclass(getattr(bpy.types, cls), bpy.types.Node)
]


class ShaderImporter(ShaderUtils):
    def __init__(
        self,
        gltf: glTFImporter,
        sc_material: ScShaderMaterial,
        material: Material,
        preset: Type[ShaderPresetDescriptor],
    ):
        self.gltf = gltf
        self.sc_material = sc_material
        self.material = material
        self.tree: ShaderNodeTree = ShaderUtils.get_node_tree(material)
        self.preset = preset
        self.output: ShaderNodeOutputMaterial

        self.node_counter = 0  # Counter for texture nodes
        self.utils_offset = -125  # Y offset for utilities nodes
        self.x_offset = 0  # X offset for all nodes
        self.image_cache: Dict[str, ShaderNodeTexImage] = {}
        self.basepath = Path(gltf.import_settings["filepath"]).parent

    def import_material(self):
        self.setup_blending()

        self.output: ShaderNodeOutputMaterial = self.tree.nodes.new(  # type: ignore
            "ShaderNodeOutputMaterial"
        )
        self.output.location = 250, 100

        modifier = self.setup_modifiers()
        self.shader = self.setup_shader()
        self.preset.import_shader(self)

        if modifier is not None:
            first, last = modifier

            self.tree.links.new(first.inputs[0], self.shader.outputs[0])
            self.tree.links.new(self.output.inputs[0], last.outputs[0])
        else:
            self.tree.links.new(self.output.inputs[0], self.shader.outputs[0])

        # Preserve unsupported shader constants
        if len(self.sc_material.unused_constants):
            self.shader["$constants"] = self.sc_material.unused_constants

        # Preserve shader name, uber by default
        if self.sc_material.shader_name != "uber":
            self.shader["$shader"] = self.sc_material.shader_name

        for variable in self.sc_material.unused_variables:
            self.set_raw_shader_prop(variable)

    def setup_modifiers(self):
        result = []

        if self.sc_material.blend_mode == ScBlendMode.SCREEN:
            result.append(self.setup_modifier("ScMultiplyModifier", "Multiply"))

        if result:
            return (result[0], result[-1])

        return None

    def setup_blending(self):
        if self.sc_material.blend_mode == ScBlendMode.OPAQUE:
            self.material.surface_render_method = "DITHERED"
        else:
            self.material.surface_render_method = "BLENDED"

    def set_raw_shader_prop(self, raw_property: Tuple[str, ShaderProperty]):
        key, prop = raw_property
        if isinstance(prop, ShaderTextureProperty):
            if not prop.path:
                return

            image = self.load_texture_image(prop, True)
            self.shader[key] = image
            return

        self.shader[key] = prop.value

    def set_constant_prop(self, name: str, index: int):
        socket = self.shader.inputs[index]

        if self.is_bool_socket(socket, name):
            socket.default_value = self.sc_material.has_constant(name)
            return True

        return False

    def load_texture_from_image(self, name: str, buffer: bytes):
        img = bpy.data.images.new(name, width=1, height=1)
        img.source = "FILE"
        img.pack(data=buffer, data_len=len(buffer))
        img.reload()
        return img

    def load_texture_from_raw(self, name: str, width: int, height, buffer: bytes):
        array = np.frombuffer(buffer, dtype=np.uint8)
        array = array.reshape((height, width, 4))
        array = np.flipud(array)

        pixels = array.astype(np.float32) / 255.0
        img = bpy.data.images.new(name, width=width, height=height, alpha=True)
        img.pixels.foreach_set(pixels.ravel())  # type: ignore
        img.update()
        img.pack()
        return img

    def load_compressed_texture(self, path: Path):
        image_converter = load_image_converter()
        loader: Dict[str, Callable[..., tuple[bytes, int, int]]] = {
            ".sctx": image_converter.decode_sctx  # type: ignore
        }

        try:
            buffer, width, height = loader[str(path.suffix)](path)
            return self.load_texture_from_raw(str(path), width, height, buffer)
        except Exception as e:
            print(e)

    def try_load_texture_image(self, path: Path) -> Image | None:
        image_converter = load_image_converter()

        IMAGE_CONVERTER_EXTENSIONS: list[str] = (
            []
            if image_converter is None
            else image_converter.SUPPORTED_CONVERTER_EXTENSIONS
        )

        lookups = ["", self.basepath]
        prefs = get_prefs()
        if prefs:
            lookups += [string.value for string in prefs.texture_lookup]

        for extension in IMAGE_EXTENSIONS:
            paths: list[Path] = []
            for lookup in lookups:
                paths += [
                    # Tweak for brawl stars, trying to use highres textures preferably
                    Path(lookup)
                    / path.parent
                    / "background"
                    / Path(path.stem)
                    .with_name(path.stem + "_highres")
                    .with_suffix(extension),  # Default
                    Path(lookup)
                    / Path(path.stem + "_highres").with_suffix(extension),  # Stem
                    # Default path
                    Path(lookup) / path.with_suffix(extension),
                    # Using path stem
                    Path(lookup) / Path(path.stem).with_suffix(extension),
                ]

            # Decoding existing on user device textures
            for maybe_path in paths:
                if not exists(maybe_path):
                    continue

                # Loading blender supported image
                if extension in NATIVE_IMAGE_EXTENSIONS:
                    return bpy.data.images.load(str(maybe_path))

                # Load using image converter
                if extension in IMAGE_CONVERTER_EXTENSIONS:
                    data = self.load_compressed_texture(maybe_path)
                    if data is not None:
                        return data

                # Converting user texture using neko api
                if extension in SUPPORTED_NEKO_EXTENSIONS:
                    with open(maybe_path, "rb") as file:
                        data = texture_loader.convert_user_texture(
                            str(path), file.read()
                        )

                    if data is not None:
                        return self.load_texture_from_image(str(path), data)

            # Trying to fetch raw textures from neko asset api
            # Iterate only by titan supported extensions
            # Using just NATIVE_IMAGE_EXTENSIONS creates a lot of
            # network requests just to guess texture name
            if extension in NATIVE_TITAN_IMAGE_EXTENSION:
                for maybe_path in paths:
                    # Check if blender can load texture with that extension
                    # Or image converter can decode it locally
                    if (
                        extension not in NATIVE_IMAGE_EXTENSIONS
                        and extension not in IMAGE_CONVERTER_EXTENSIONS
                    ):
                        continue

                    result = texture_loader.download_raw_texture(maybe_path.as_posix())
                    if result is None:
                        continue

                    texture_path, data = result

                    # Decoding with image converter
                    if extension in IMAGE_CONVERTER_EXTENSIONS:
                        return self.load_compressed_texture(Path(texture_path))

                    # Loading from cached native image
                    if data:
                        return self.load_texture_from_image(str(path), data)

            # Trying to decode textures using neko api and its asset database
            # Works only for asset browser
            if extension in SUPPORTED_NEKO_EXTENSIONS:
                for maybe_path in paths:
                    data = texture_loader.convert_texture(str(maybe_path.as_posix()))
                    if data:
                        return self.load_texture_from_image(str(path), data)

    def load_texture_image(
        self, prop: ShaderTextureProperty, preserve_path: bool = False
    ) -> Image:
        # Using gltf images as our cache
        # Should be more reliable for some edge cases
        self.gltf.data.images = self.gltf.data.images or []
        gltf_images = [
            image
            for image in self.gltf.data.images
            if image.uri == prop.path and image.blender_image_name is not None
        ]
        if len(gltf_images) > 0:
            name = gltf_images[0].blender_image_name
            image = bpy.data.images[name]
            return image

        path = Path(prop.path)
        extension = path.suffix

        if extension == ".sc":
            print(
                f"Supercell Flash as textures not supported now. Creating empty texture for '{path}'"
            )
            preserve_path = True

        # Special handle for textures in custom properties
        # Since they dont have nodes in shader graph, it would be good if we preserve keywords at least in image name
        name = Path(prop.value) if preserve_path else Path(path.name)

        def cache_image(image: Image):
            gltf_image = glImage(None, None, None, None, prop.path, prop.path)
            gltf_image.blender_image_name = image.name  # type: ignore
            self.gltf.data.images.append(gltf_image)
            image.colorspace_settings.name = "scene_linear"  # type: ignore
            image.use_view_as_render = True

        def fallback():
            image = bpy.data.images.new(str(name), 1, 1)
            cache_image(image)
            return image

        # Firstly, trying to load texture as it is, and if blender supports that extension
        absolute_path = join(self.basepath, prop.path)
        if exists(absolute_path) and extension in NATIVE_IMAGE_EXTENSIONS:
            image = bpy.data.images.load(absolute_path)
            cache_image(image)
            return image

        # Finally, trying to load image with different extension and basepaths
        image = self.try_load_texture_image(path)
        if image is None:
            print(
                f"Failed to load texture while generating SC IO materials: {prop.path}. Creating empty image..."
            )
            return fallback()

        # Success
        image.name = prop.path
        cache_image(image)
        return image

    def _set_texture_prop_internal(self, name: str, index: int):
        prop = self.sc_material.get_property(name, ShaderTextureProperty)

        if prop is None:
            # Often textures leave a color, it needs to be marked as read
            self.sc_material.get_property(name, ShaderFloatVectorProperty)
            return

        if not prop.path:
            return

        node = self.image_cache.get(prop.path)  # type: ignore
        if node is None:
            texture: ShaderNodeTexImage = self.tree.nodes.new(
                "ShaderNodeTexImage"
            )  # type: ignore
            texture.image = self.load_texture_image(prop)

            x, y = self.shader.location

            # Base horizontal offset
            x -= 465

            # Vertical offset based on current node count and number
            if self.node_counter and self.node_counter % 3 == 0:
                x -= 300
                y -= (self.node_counter / 2) * 100
            else:
                y -= self.node_counter * 280

            texture.location = x, y
            texture.extension = "REPEAT" if "repeat" in prop.keywords else "CLIP"
            self.node_counter += 1
            node = self.image_cache[prop.path] = texture

        self.tree.links.new(self.shader.inputs[index], node.outputs[0])  # type: ignore
        return node

    def set_texture_prop(self, name: str, index: int):
        return self._set_texture_prop_internal(name, index) is not None

    def set_color_prop(self, name: str, index: int):
        prop = self.sc_material.get_property(name, ShaderFloatVectorProperty)

        if prop is None:
            return False

        socket = self.shader.inputs[index]
        if self.is_color_socket(socket, name):
            socket.default_value = prop.vector
            return True

        return False

    def set_surface_color(
        self,
        name: str,
        tex_name: str,
        index: int,
        vector: Optional[NodeSocket] = None,
        **kwargs,
    ):
        node = self._set_texture_prop_internal(tex_name, index)
        if (
            vector is not None
            and node is not None
            and self.material.node_tree is not None
        ):
            self.material.node_tree.links.new(node.inputs[0], vector)

        valid = self.set_color_prop(name, index)
        # Trying to set as float
        if not valid:
            valid = self.set_float_prop(name, index)

        return valid or node is not None

    def set_float_prop(self, name: str, index: int):
        socket = self.shader.inputs[index]
        if not self.is_float_socket(socket, name):
            return False

        float_prop = self.sc_material.get_property(name, ShaderFloatProperty)

        if float_prop:
            socket.default_value = float_prop.number
            return False

        # Sometimes floats are saved as color, as if after conversion or something
        # Bruh, based supercell devs
        # so trying to get it as color
        vector_prop = self.sc_material.get_property(name, ShaderFloatVectorProperty)
        if vector_prop and len(vector_prop.value):
            socket.default_value = vector_prop.value[0]

        return True

    def set_bool_prop(self, name: str, index: int):
        prop = self.sc_material.get_property(name, ShaderBooleanProperty)

        if prop is None:
            return False

        socket = self.shader.inputs[index]
        if self.is_bool_socket(socket, name):
            socket.default_value = prop.status
            return True

        return False

    def setup_shader(self) -> Node:
        if self.preset.shader_idname in NATIVE_NODES:
            node = self.tree.nodes.new(self.preset.shader_idname)
        else:
            node = LibraryLoader.instantiate_shader(
                self.tree, self.preset.shader_idname
            )

        node.label = self.preset.shader_label
        node.location = 40 - node.width - self.x_offset, 100

        return node

    def setup_modifier(self, id: str, label: str):
        node = LibraryLoader.instantiate_utility(self.tree, id)

        node.label = label

        # Base horizontal offset
        x = -self.x_offset
        y = 100
        self.x_offset += node.width + 50

        node.location = x, y

        return node

    def instantiate_utility(self, id: str, label: str):
        node = LibraryLoader.instantiate_utility(self.tree, id)

        node.label = label
        x, y = self.shader.location

        # Base horizontal offset
        x -= 1040 + self.x_offset
        y = self.utils_offset
        self.utils_offset -= node.height + 50

        node.location = x, y

        return node
