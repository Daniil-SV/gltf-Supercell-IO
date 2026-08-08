from . import ScwChunk, BinaryReader
from .sub.node import ScwNode
from typing import Tuple
from dataclasses import dataclass

@dataclass
class ScwNodes(ScwChunk):
    nodes: Tuple[ScwNode, ...] = ()

    def __br_read__(self, br: BinaryReader) -> None:
        nodes_count = br.read_uint16()
        self.nodes = br.read_struct(ScwNode, nodes_count)
