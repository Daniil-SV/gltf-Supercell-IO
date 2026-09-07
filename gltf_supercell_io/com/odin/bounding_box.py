import numpy as np
from typing import Self


class BoundingBox:
    def __init__(self) -> None:
        self.info = np.finfo(np.float32)
        self.min = np.full((3,), self.info.max, dtype=np.float32)
        self.max = np.full((3,), self.info.min, dtype=np.float32)

    def extend(self, array: np.ndarray):
        bbox_min = array.min(axis=0)
        bbox_max = array.max(axis=0)
        return self.union_point(bbox_min, bbox_max)

    def union_point(self, bbox_min: np.ndarray, bbox_max: np.ndarray):
        self.min = np.minimum(self.min, bbox_min)
        self.max = np.maximum(self.max, bbox_max)
        return self

    def union(self, other: Self):
        return self.union_point(other.min, other.max)

    @property
    def empty(self):
        return bool(
            np.all(self.min == self.info.max) and np.all(self.max == self.info.min)
        )

    def as_list(self):
        if self.empty:
            return [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]

        return [self.min.tolist(), self.max.tolist()]

    def as_flat_list(self):
        if self.empty:
            return [0.0] * 6
        return self.min.tolist() + self.max.tolist()
