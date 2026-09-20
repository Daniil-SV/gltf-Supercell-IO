from dataclasses import dataclass, field

from mathutils import Matrix

from .. import BinaryReader, ScwChunk


@dataclass
class ScwJoint(ScwChunk):
    name = ""
    inverse_bind_matrix: Matrix = field(default_factory=Matrix)

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.name = br.read_str() or ""
        self.inverse_bind_matrix = br.read_matrix()
