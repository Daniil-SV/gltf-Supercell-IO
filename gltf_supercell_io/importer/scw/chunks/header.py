from typing import Optional
from . import ScwChunk, BinaryReader
from dataclasses import dataclass


@dataclass
class ScwHeader(ScwChunk):
    version = -1
    frame_rate = 30
    frame_start = 0
    frame_end = 0
    materials_file: Optional[str] = None

    def __br_read__(self, br: "BinaryReader"):
        self.version, self.frame_rate, self.frame_start, self.frame_end = (
            br.read_uint16(4)
        )

        self.materials_file = br.read_str()

        if self.version > 1:
            br.read_uint8()  # Clipping or smth
