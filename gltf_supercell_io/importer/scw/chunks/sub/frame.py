from .. import ScwChunk, BinaryReader
from typing import Self
from dataclasses import dataclass, field
from mathutils import Quaternion, Vector


@dataclass
class ScwFrame(ScwChunk):
    index = 0
    translation: Vector = field(default_factory=Vector)
    rotation: Quaternion = field(default_factory=Quaternion)
    scale: Vector = field(default_factory=lambda: Vector((1, 1, 1)))

    def __br_read__(
        self,
        br: "BinaryReader",
        flags=0,
        structs: list[Self] = [],
        index=0,
        *args,
        **kwargs
    ) -> None:
        if index == 0:
            flags = 0xFF
            base_frame = ScwFrame()
        else:
            base_frame = structs[index - 1]

        self.index = br.read_uint16()

        if (flags & 1) != 0:
            self.rotation = Quaternion(br.read_norm_half_float(4))
        else:
            self.rotation = base_frame.rotation

        if (flags & 2) != 0:
            self.translation.x = br.read_float()
        else:
            self.translation.x = base_frame.translation.x

        if (flags & 4) != 0:
            self.translation.y = br.read_float()
        else:
            self.translation.y = base_frame.translation.y

        if (flags & 8) != 0:
            self.translation.z = br.read_float()
        else:
            self.translation.z = base_frame.translation.z

        if (flags & 16) != 0:
            self.scale.x = br.read_float()
        else:
            self.scale.x = base_frame.scale.x

        if (flags & 32) != 0:
            self.scale.y = br.read_float()
        else:
            self.scale.y = base_frame.scale.y

        if (flags & 64) != 0:
            self.scale.z = br.read_float()
        else:
            self.scale.z = base_frame.scale.z
