from dataclasses import dataclass

from .geometry_instance import ScwGeometryInstance


# Essentially the same but with skinning binding
@dataclass
class ScwControllerInstance(ScwGeometryInstance):
    pass
