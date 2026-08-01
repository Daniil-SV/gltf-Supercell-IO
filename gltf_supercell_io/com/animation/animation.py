from .reader import OdinAnimationReader
from .rawReader import OdinRawAnimationReader
from .packedReader import OdinPackedReader
from .continuousPackedReader import OdinContinuousPackedReader
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter


class OdinAnimation:
    """Supercell odin animation reader"""

    @staticmethod
    def CreatePackedReader(gltf: glTFImporter, descriptor: dict) -> OdinPackedReader:
        packed: dict = descriptor.get("packed")  # type: ignore
        if packed.get("uintAccessor") is not None:
            return OdinContinuousPackedReader(gltf, descriptor)

        return OdinPackedReader(gltf, descriptor)

    @staticmethod
    def Create(gltf: glTFImporter, descriptor: dict) -> OdinAnimationReader:
        """Animation reader factory"""
        result = None
        if (
            descriptor.get("nodes") is not None
            and descriptor.get("accessor") is not None
        ):
            result = OdinRawAnimationReader(gltf, descriptor)

        if descriptor.get("packed") is not None:
            result = OdinAnimation.CreatePackedReader(gltf, descriptor)

        if result is None:
            raise NotImplementedError("Unknown animation data")

        result.read()
        return result
