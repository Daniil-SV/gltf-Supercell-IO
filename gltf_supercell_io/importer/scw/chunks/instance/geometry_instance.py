from . import ScwInstance, BinaryReader
from dataclasses import dataclass, field


@dataclass
class ScwGeometryInstance(ScwInstance):
    target_mesh: str = ""
    material_binding: dict[str, str] = field(default_factory=dict)

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.target_mesh = br.read_str() or ""
        materials_count = br.read_uint16()

        for _ in range(materials_count):
            source = br.read_str() or ""
            target = br.read_str() or ""
            self.material_binding[source] = target
