from .geometry_instance import ScwGeometryInstance
from dataclasses import dataclass


# Essentially the same but with skinning binding
@dataclass
class ScwControllerInstance(ScwGeometryInstance):
    pass
