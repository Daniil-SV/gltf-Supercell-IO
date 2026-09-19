from typing import List
from ..odin.animation_flags import OdinAnimationFlags
from .packedReader import OdinPackedReader
from ..odin.animation import TRANSLATION_CHANNELS, ROTATION_CHANNELS, SCALE_CHANNELS
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
import numpy as np


class OdinRlePackedReader(OdinPackedReader):
    def __init__(self, gltf: glTFImporter, animation):
        super().__init__(gltf, animation)

        self.rotation_data = None
        rotation_accessor_idx = self.descriptor.get("uintAccessor")
        if rotation_accessor_idx is not None:
            self.rotation_counter = 0
            self.rotation_data = BinaryData.decode_accessor(gltf, rotation_accessor_idx)
            self.stride = 8

        self.elements_counter = 0

    def read_normalized_transforms(self, frame_count: int, flags: OdinAnimationFlags):
        rotation = [
            np.zeros(frame_count, dtype=np.int16) for _ in range(ROTATION_CHANNELS)
        ]
        translation = [
            np.zeros(frame_count, dtype=np.int16) for _ in range(TRANSLATION_CHANNELS)
        ]
        scale = [np.zeros(frame_count, dtype=np.int16) for _ in range(SCALE_CHANNELS)]

        if not flags.has_transform or frame_count == 0:
            return (translation, rotation, scale)

        frame_index = 0
        while frame_count > frame_index:
            run_length = int(self.read_normalized_value())
            if run_length == 0:
                raise Exception("Frame run length cannot be zero!")

            remaining_frames = frame_count - frame_index
            if abs(run_length) > remaining_frames:
                raise Exception("Frame run length is too big!")

            if run_length > 0:
                for _ in range(run_length):
                    if frame_index >= frame_count:
                        break

                    if flags.has_tracktime:
                        self.read_normalized_value()

                    if flags.has_rotation:
                        for i in range(ROTATION_CHANNELS):
                            rotation[i][frame_index] = self.read_normalized_value()

                    if flags.has_translation:
                        for i in range(TRANSLATION_CHANNELS):
                            translation[i][frame_index] = self.read_normalized_value()

                    if flags.has_scale:
                        if flags.has_scale3D:
                            for i in range(SCALE_CHANNELS):
                                scale[i][frame_index] = self.read_normalized_value()
                        else:
                            val = self.read_normalized_value()
                            for i in range(SCALE_CHANNELS):
                                scale[i][frame_index] = val

                    frame_index += 1

            elif run_length < 0:
                repeat_count = -run_length

                for _ in range(repeat_count):
                    if frame_index >= frame_count:
                        break

                    prev = frame_index - 1
                    if prev >= 0:
                        if flags.has_rotation:
                            for i in range(ROTATION_CHANNELS):
                                rotation[i][frame_index] = rotation[i][prev]

                        if flags.has_translation:
                            for i in range(TRANSLATION_CHANNELS):
                                translation[i][frame_index] = translation[i][prev]

                        if flags.has_scale:
                            for i in range(SCALE_CHANNELS):
                                scale[i][frame_index] = scale[i][prev]

                    frame_index += 1

        if self.elements_counter != self.data_size:
            raise Exception(
                "The number of read elements does not match the actual size of the node"
            )

        self.elements_counter = 0
        return (translation, rotation, scale)

    def read_normalized_value(self) -> int | float:
        result = self.normalized_transform_data[self.transform_index].item()
        self.transform_index += 1
        if self.elements_counter >= self.data_size:
            raise Exception("Transform index exceeded data size limit")

        self.elements_counter += 1
        return result

    def read_base_rotation(self) -> List[int]:
        if self.rotation_data is None:
            return super().read_base_rotation()

        result = [
            self.rotation_data[self.rotation_counter + i] / 32767.0
            for i in range(ROTATION_CHANNELS)
        ]
        self.rotation_counter += ROTATION_CHANNELS
        return result
