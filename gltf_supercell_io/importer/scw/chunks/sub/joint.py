from .. import ScwChunk, BinaryReader
from mathutils import Matrix
from dataclasses import dataclass, field


@dataclass
class ScwJoint(ScwChunk):
    name = ""
    inverse_bind_matrix: Matrix = field(default_factory=Matrix)

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.name = br.read_str()
        self.inverse_bind_matrix = br.read_matrix()
