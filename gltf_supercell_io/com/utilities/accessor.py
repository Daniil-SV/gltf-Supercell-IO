from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class MemoryAccessor:
    """Small wrapper for ndarray so we can pass some preprocessed
    memory ndarray almost directly to gltf importer, without any back encoding overhead
    """

    value: np.ndarray

    @property
    def count(self):
        return len(self.value)
