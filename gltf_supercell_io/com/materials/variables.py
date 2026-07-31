from typing import List, Dict
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.com.gltf2_io import Image, Texture
from ..utilities import is_typed_array
from collections import OrderedDict
from typing import Any, Optional


class ShaderProperty:
    """Base shader property"""

    def __init__(self, value: Any = None):
        pass

    @property
    def value(self) -> Any:
        return None


class ShaderFloatProperty(ShaderProperty):
    """Shader float property"""

    def __init__(self, value: float = 0.0):
        if not isinstance(value, (float, int)):
            raise TypeError("Incorrect float property value type")
        self.number = float(value)

    @property
    def value(self) -> Any:
        return self.number


class ShaderFloatVectorProperty(ShaderProperty):
    """Shader float vector property"""

    def __init__(self, vector: List[float] = []):
        if not is_typed_array(vector, (float, int)):
            raise TypeError("Incorrect float array property value type")

        self.vector = [float(num) for num in vector]

    @property
    def value(self) -> Any:
        return self.vector


class ShaderTextureProperty(ShaderProperty):
    """Shader texture property"""

    def __init__(self, data: str | Texture):
        self.path: str = ""
        self.keywords: List[str] = []
        self.texture: Optional[Texture] = None

        if isinstance(data, str):
            self.set_path(data)
        elif isinstance(data, Texture):
            self.texture = data
        else:
            raise TypeError("Incorrect texture property value type")

    def set_path(self, path: str):
        self.path = path
        self.keywords = []

        if "#" in path:
            path, keywords = path.split("#")
            self.path = path
            self.keywords = keywords.split("+") or []

    @property
    def extension(self):
        return self.path.split(".")[-1]

    @property
    def value(self) -> Any:
        if self.texture is not None:
            return {"index": self.texture}

        if len(self.keywords) == 0:
            return self.path

        return f"{self.path}#{'+'.join(self.keywords)}"


class ShaderBooleanProperty(ShaderProperty):
    """Shader boolean property"""

    def __init__(self, value: bool = False):
        if not isinstance(value, bool):
            raise TypeError("Incorrect boolean property value type")

        self.status = bool(value)

    @property
    def value(self) -> Any:
        return self.status


class ScShaderVariables:
    """Container class for managing shader properties in a glTF import pipeline"""

    def __init__(self):
        self.properties: Dict[str, ShaderProperty] = OrderedDict()

    def from_booleans(self, data: Dict[str, Any]):
        """Load boolean properties from dictionary"""
        for key, value in data.items():
            self.properties[key] = ShaderBooleanProperty(value)

    def to_dict(self, filter_type=None):
        properties = self.properties
        if filter_type is not None:
            properties = {
                key: prop
                for key, prop in properties.items()
                if isinstance(prop, filter_type)
            }

        return {key: prop.value for key, prop in properties.items()}

    @property
    def boolean_properties(self):
        return self.to_dict(ShaderBooleanProperty)

    def from_float_vectors(self, data: Dict[str, Any]):
        """Load float vector properties from dictionary"""
        for key, value in data.items():
            self.properties[key] = ShaderFloatVectorProperty(value)

    @property
    def float_array_properties(self):
        return self.to_dict(ShaderFloatVectorProperty)

    def from_floats(self, data: Dict[str, Any]):
        """Load float properties from dictionary"""
        for key, value in data.items():
            self.properties[key] = ShaderFloatProperty(value)

    @property
    def float_properties(self):
        return self.to_dict(ShaderFloatProperty)

    def from_textures(self, data: Dict[str, Any]):
        """Load texture properties from dictionary"""
        for key, value in data.items():
            self.properties[key] = ShaderTextureProperty(value)

    @property
    def texture_properties(self):
        return self.to_dict(ShaderTextureProperty)

    def from_dict(self, gltf: glTFImporter, data: Dict[str, Any]):
        """Load properties from dictionary"""
        self.properties = OrderedDict()

        typed_vectors = {
            "floatVectors": self.from_float_vectors,
            "floats": self.from_floats,
            "textures": self.from_textures,
            "booleans": self.from_booleans,
        }

        for key, value in data.items():
            if key in typed_vectors:
                typed_vectors[key](value)
                continue

            # From raw value
            if isinstance(value, list):
                self.properties[key] = ShaderFloatVectorProperty(value)
            elif isinstance(value, float):
                self.properties[key] = ShaderFloatProperty(value)
            elif isinstance(value, dict) and (idx := value.get("index")) is not None:
                uri = ""
                if len(gltf.data.textures) > idx:
                    texture: Texture = gltf.data.textures[idx]
                    image: Image = gltf.data.images[texture.source]
                    uri = image.uri or ""
                self.properties[key] = ShaderTextureProperty(uri)
            elif isinstance(value, bool):
                self.properties[key] = ShaderBooleanProperty(value)

    def to_typed_dict(self):
        return {
            "booleans": self.boolean_properties,
            "floatVectors": self.float_array_properties,
            "floats": self.float_properties,
            "textures": self.texture_properties,
        }
