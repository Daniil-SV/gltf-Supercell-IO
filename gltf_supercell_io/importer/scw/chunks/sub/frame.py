from .. import ScwChunk, BinaryReader
from typing import Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Vector:
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None

    @property
    def values(self):
        return (self.x, self.y, self.z)

@dataclass
class ScwFrame(ScwChunk):
    index = 0
    translation: Vector = field(default_factory=Vector)
    rotation: Optional[Tuple[float, ...]] = None
    scale: Vector = field(default_factory=Vector)

    def __br_read__(self, br: "BinaryReader", flags=0) -> None:
        self.index = br.read_uint16()

        if (flags & 1) == 0:
            self.rotation = br.read_norm_half_float(4)

        if (flags & 2) == 0:
            self.translation.x = br.read_float()

        if (flags & 4) == 0:
            self.translation.y = br.read_float()

        if (flags & 8) == 0:
            self.translation.z = br.read_float()

        if (flags & 16) == 0:
            self.scale.x = br.read_float()

        if (flags & 32) == 0:
            self.scale.y = br.read_float()

        if (flags & 64) == 0:
            self.scale.z = br.read_float()
