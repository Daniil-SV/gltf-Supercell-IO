from .reader import OdinAnimationReader
from .reader import TranslationChannels, RotationChannels, ScaleChannels
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
import numpy as np


class OdinRawAnimationReader(OdinAnimationReader):
    def __init__(self, gltf: glTFImporter, animation: dict):
        super().__init__(animation)

        self.used_nodes = animation.get("nodes")  # type: ignore
        self.keyframe_mapping = animation.get("keyframeCounts")

        nodes_per_keyframe: list[int] = animation.get(
            "nodesNumberPerKeyframe"
        )  # type: ignore
        if self.keyframe_mapping:
            self.keyframe_mapping = [
                num
                for i, num in enumerate(self.keyframe_mapping)
                for _ in range(nodes_per_keyframe[i])
            ]

        self.buffer = BinaryData.decode_accessor(gltf, animation.get("accessor"))

        self.translation: list[list[list[float]]] = [
            [[] for _ in range(TranslationChannels)]
            for _ in range(len(self.used_nodes))
        ]
        self.rotation: list[list[list[float]]] = [
            [[] for _ in range(RotationChannels)] for _ in range(len(self.used_nodes))
        ]
        self.scale: list[list[list[float]]] = [
            [[] for _ in range(ScaleChannels)] for _ in range(len(self.used_nodes))
        ]

    def read(self):
        keyframes_total = (
            sum(self.keyframe_mapping) if self.keyframe_mapping else self.keyframe_count
        )

        # Position + Quaternion Rotation + Scale
        frame_transform_length = 3 + 4 + 3
        if self.keyframe_mapping:
            remapped = np.reshape(
                self.buffer, (keyframes_total, frame_transform_length)
            )
            data = np.split(
                remapped, np.cumsum(self.keyframe_mapping)[:-1]
            )  # type: ignore
        else:
            data = np.reshape(
                self.buffer,
                (len(self.used_nodes), self.keyframe_count, frame_transform_length),
            )

        for node_index in range(len(self.used_nodes)):
            for frame_index in range(self.node_keyframes(node_index)):
                t, r, s = np.split(data[node_index][frame_index], [3, 7])

                for i in range(TranslationChannels):
                    self.translation[node_index][i].append(t[i])

                for i in range(RotationChannels):
                    self.rotation[node_index][i].append(r[i])

                for i in range(ScaleChannels):
                    self.scale[node_index][i].append(s[i])

    def node_keyframes(self, node_idx: int):
        if self.keyframe_mapping:
            return self.keyframe_mapping[node_idx]
        return self.keyframe_count

    def get_scale(self, node_idx: int):
        return self.scale[node_idx]

    def get_translation(self, node_idx: int):
        return self.translation[node_idx]

    def get_rotation(self, node_idx: int):
        return self.rotation[node_idx]
