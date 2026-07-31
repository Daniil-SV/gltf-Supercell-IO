from typing import List, Dict, Tuple
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from .variables import ScShaderVariables, ShaderProperty
from enum import IntEnum
from typing import TypeVar, Any, Type, Optional

T = TypeVar("T", bound="ShaderProperty")


class ScBlendMode(IntEnum):
    ALPHA_ADDITIVE = 6
    ALPHA = 5
    OPAQUE = 4
    SCREEN = 3
    MULTIPLY = 2
    ADDITIVE = 1
    PREMULTIPLIED = 0


class ScShaderMaterial:
    def __init__(self):
        # Name of material
        self.name = ""

        # Index of blending mode
        self.blend_mode = ScBlendMode.OPAQUE

        # Array of string which describes which shader features material should use
        self._constants: List[str] = []

        # Settings variables for shader
        self._variables = ScShaderVariables()

        # Name of material shader
        self.shader_name = ""

        self._used_variables = set()
        self._used_constants = set()

    def has_constant(self, key: str) -> bool:
        """Check if constant is used"""
        if key in self._constants:
            self._used_constants.add(key)
            return True

        return False

    def add_constant(self, key: str):
        """Add constant to material"""
        self._constants.append(key)

    def get_property(
        self, key: str, desired_type: Optional[Type[T]] = None
    ) -> Optional[T]:
        """Get property from material"""
        if key in self._variables.properties:
            result = self._variables.properties[key]
            if desired_type is not None and not isinstance(result, desired_type):
                return None

            self._used_variables.add(key)
            return result  # type: ignore

        return None

    def add_property(self, key: str, value: Any, type: Type[T]) -> T:
        instance = type(value)
        self._variables.properties[key] = instance
        return instance

    @property
    def unused_constants(self) -> List[str]:
        """Get unused constants"""
        return [
            constant
            for constant in self._constants
            if constant not in self._used_constants
        ]

    @property
    def unused_variables(self) -> List[Tuple[str, ShaderProperty]]:
        """Get unused variables"""
        return [
            (key, prop)
            for key, prop in self._variables.properties.items()
            if key not in self._used_variables
        ]

    def from_dict(self, gltf: glTFImporter, data: Dict[str, Any]):
        """Load material from dictionary"""
        self.name = str(data.get("name", ""))
        self.blend_mode = ScBlendMode(int(data.get("blendMode", 4)))
        self._constants = list(data.get("constants", []))
        self.shader_name = str(data.get("shader", ""))

        self._variables.from_dict(gltf, data.get("variables", {}))

    def to_typed_dict(self):
        return {
            "blendMode": int(self.blend_mode),
            "constants": self._constants,
            "name": self.name,
            "shader": self.shader_name or "uber",
            "variables": self._variables.to_typed_dict(),
        }

    def to_dict(self):
        """Save material to dictionary"""
        return {
            "blendMode": int(self.blend_mode),
            "constants": self._constants,
            "name": self.name,
            "sc_material": True,
            "shader": self.shader_name or "uber",
            "variables": self._variables.to_dict(),
        }
