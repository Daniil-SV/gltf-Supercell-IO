from dataclasses import dataclass
from typing import Optional

from . import BinaryReader, ScwChunk


@dataclass
class ScwHeader(ScwChunk):
    version = -1
    frame_rate = 30
    frame_start = 0
    frame_end = 0
    reference_file: Optional[str] = None

    def __br_read__(self, br: "BinaryReader", end_offset=-1, *args, **kwargs):
        self.version, self.frame_rate, self.frame_start, self.frame_end = (
            br.read_uint16(4)
        )

        self.reference_file = br.read_str()
        if end_offset > br.pos() and self.version >= 1:
            br.read_bool() # Used in Scene::updateInstanceTransformations
