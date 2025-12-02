from typing import List, Dict, Tuple
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from .variables import ScShaderVariables, ShaderProperty
from enum import IntEnum

class ScBlendMode(IntEnum):
    Opaque = 4
    Clip = 2 # Not sure about that
    Hashed = 1 # And this too
    Blend = 0

class ScShaderMaterial:
    def __init__(self):
        # Name of material
        self.name = ""
        
        # Index of blending mode
        self.blend_mode = ScBlendMode.Opaque
        
        # Array of string which describes which shader features material should use
        self._constants: List[str] = []
        
        # Settings variables for shader
        self._variables = ScShaderVariables()
        
        # Name of material shader
        self.shader_name = ""

        self._used_variables = set()
        self._used_constants = set()
        
    def has_constant(self, key: str) -> bool:
        if (key in self._constants):
            self._used_constants.add(key)
            return True
        
        return False
    
    def get_property(self, key: str, desired_type = None) -> ShaderProperty | None:
        if (key in self._variables.properties):
            result = self._variables.properties[key]
            if (desired_type is not None and not isinstance(result, desired_type)):
                return None
            
            self._used_variables.add(key)
            return result
        
        return None
    
    @property
    def unused_constants(self) -> List[str]:
        return [constant for constant in self._constants if constant not in self._used_constants]
    
    @property
    def unused_variables(self) -> List[Tuple[str, ShaderProperty]]:
        return [(key, prop) for key, prop in self._variables.properties.items() if key not in self._used_variables]
        
    def from_dict(self, gltf: glTFImporter, data: Dict[str, any]):
        self.name = str(data.get("name", ""))
        self.blend_mode = ScBlendMode(int(data.get("blendMode", 4)))
        self._constants = list(data.get("constants", []))
        self.shader_name = str(data.get("shader", ""))
        
        self._variables.from_dict(gltf, data.get("variables", {}))
        