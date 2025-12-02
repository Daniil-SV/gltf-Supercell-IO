from typing import List, Dict
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.com.gltf2_io import Image

class ShaderProperty:
    def __init__(self):
        pass
    
    @property
    def value(self) -> any:
        return None
        
class ShaderFloatProperty(ShaderProperty):
    def __init__(self, value: float = 0.0):
        self.number = float(value)
        
    @property
    def value(self) -> any:
        return self.number

class ShaderFloatVectorProperty(ShaderProperty):
    def __init__(self, vector: List[float] = []):
        self.vector = list(vector)
        
    @property
    def value(self) -> any:
        return self.vector
        
class ShaderTextureProperty(ShaderProperty):
    def __init__(self, path: str = ""):
        self.texture_path = path
        self.keywords: List[str] = []
        
        if ("#" in path):
            path, keywords = path.split("#")
            self.texture_path = path
            self.keywords = keywords.split("+")
            
    @property
    def value(self) -> any:
        return self.texture_path
            
class ShaderBooleanProperty(ShaderProperty):
    def __init__(self, value: bool = False):
        self.status = bool(value)
        
    @property
    def value(self) -> any:
        return self.status

class ScShaderVariables:
    def __init__(self):
        self.properties: Dict[str, ShaderProperty] = {}
        
    def from_booleans(self, data: Dict[str, any]):
        for key, value in data.items():
            self.properties[key] = ShaderBooleanProperty(value) 
        
    def from_float_vectors(self, data: Dict[str, any]):
        for key, value in data.items():
            self.properties[key] = ShaderFloatVectorProperty(value) 
    
    def from_floats(self, data: Dict[str, any]):
        for key, value in data.items():
            self.properties[key] = ShaderFloatProperty(value) 
    
    def from_textures(self, data: Dict[str, any]):
        for key, value in data.items():
            self.properties[key] = ShaderTextureProperty(value) 
        
    def from_dict(self, gltf: glTFImporter, data: Dict[str, any]):
        self.properties = {}
        
        typed_vectors = {
            "floatVectors": self.from_float_vectors,
            "floats": self.from_floats,
            "textures": self.from_textures,
            "booleans": self.from_booleans
        }
        
        for key, value in data.items():
            if (key in typed_vectors):
                typed_vectors[key](value)
                continue
            
            # From raw value
            if (isinstance(value, list)):
                self.properties[key] = ShaderFloatVectorProperty(value)
            elif (isinstance(value, float)):
                self.properties[key] = ShaderFloatProperty(value)
            elif (isinstance(value, dict) and (idx := value.get("index")) is not None):
                image: Image = gltf.data.images[idx]
                self.properties[key] = ShaderTextureProperty(image.uri or "")
            elif (isinstance(value, bool)):
                self.properties[key] = ShaderBooleanProperty(value)