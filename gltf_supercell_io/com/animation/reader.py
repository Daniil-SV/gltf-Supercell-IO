from typing import List, Sequence
from .flags import OdinAnimationFlags

RotationChannels = 4
TranslationChannels = 3
ScaleChannels = 3


class OdinAnimationReader:
    def __init__(self, animation: dict):
        self.frame_rate: float = animation.get("frameRate") or 30.0
        self.frame_spf: float = 1.0 / self.frame_rate
        self.keyframe_count: int = (
            animation.get("keyframesCount") or animation.get("keyframeCount")
        ) or 1
        self.nodes_per_keyframe = animation.get("nodesNumberPerKeyframe")
        self.keyframe_mapping: List[int] | None = None
        self.used_nodes: List[int] = []

    def get_node_flags(self, node_idx: int):
        return OdinAnimationFlags(0xFF)

    def read(self):
        """Reads buffer data"""
        raise NotImplementedError()

    def get_scale(self, node_idx: int) -> Sequence[Sequence[float]] | None:
        """Returns scale keyframes for the given node index"""
        return None

    def get_translation(self, node_idx: int) -> Sequence[Sequence[float]] | None:
        """Returns translation keyframes for the given node index"""
        return None

    def get_rotation(self, node_idx: int) -> Sequence[Sequence[float]] | None:
        """Returns rotation keyframes for the given node index"""
        return None
