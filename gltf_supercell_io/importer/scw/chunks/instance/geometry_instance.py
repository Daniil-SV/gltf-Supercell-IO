from . import ScwInstance, BinaryReader
from typing import Tuple


class ScwGeometryInstance(ScwInstance):
    target_mesh = ""
    material_binding: Tuple[Tuple[str, str], ...] = ()

    def __br_read__(self, br: "BinaryReader"):
        self.target_mesh = br.read_str()
        materials_count = br.read_uint16()

        bindings = []
        for _ in range(materials_count):
            source = br.read_str()
            target = br.read_str()
            bindings.append((source or "", target or ""))

        self.material_binding = tuple(bindings)
