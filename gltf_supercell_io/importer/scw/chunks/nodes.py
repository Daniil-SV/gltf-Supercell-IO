from dataclasses import dataclass

from . import BinaryReader, ScwChunk
from .sub.node import ScwNode


@dataclass
class ScwNodes(ScwChunk):
    nodes: tuple[ScwNode, ...] = ()

    def __br_read__(self, br: BinaryReader, version=-1, *args, **kwargs) -> None:
        nodes_count = br.read_uint16()
        self.nodes = br.read_struct(ScwNode, nodes_count, version=version)
