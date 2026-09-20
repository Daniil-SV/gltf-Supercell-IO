from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter

from .packed_reader import OdinPackedReader
from .raw_reader import OdinRawAnimationReader
from .reader import OdinAnimationReader
from .rle_reader import OdinRlePackedReader


class OdinAnimation:
    """
    Supercell odin animation reader
    The implementation of this class completely diverges from the real one
    in favor of such a design in order to support all versions of
    odin animation that used by Supercell
    """

    @staticmethod
    def CreatePackedReader(gltf: glTFImporter, descriptor: dict) -> OdinPackedReader:
        packed: dict = descriptor.get("packed")  # type: ignore
        if packed.get("uintAccessor") is not None:
            return OdinRlePackedReader(gltf, descriptor)

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
