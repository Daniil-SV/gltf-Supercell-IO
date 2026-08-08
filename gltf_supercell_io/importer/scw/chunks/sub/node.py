from .frame import ScwFrame
from ..instance import ScwInstance
from ..instance.geometry_instance import ScwGeometryInstance
from ..instance.controller_instance import ScwControllerInstance
from ..instance.camera_instance import ScwCameraInstance
from .. import ScwChunk, BinaryReader
from dataclasses import dataclass
from typing import Optional

@dataclass
class ScwNode(ScwChunk):
    name = ""
    parent: Optional[str] = None
    instances: tuple[ScwInstance, ...] = ()
    frames: tuple[ScwFrame, ...] = ()

    def __br_read__(self, br: "BinaryReader", version=-1, *args, **kwargs) -> None:
        self.name = br.read_str()
        self.parent = br.read_str()

        instances_count = br.read_uint16()
        instances = []
        for _ in range(instances_count):
            instance_name = br.read_bytes(4)

            match instance_name:
                case b"CONT":
                    instances.append(br.read_struct(ScwControllerInstance))
                case b"GEOM":
                    instances.append(br.read_struct(ScwGeometryInstance))
                case b"CAME":
                    instances.append(br.read_struct(ScwCameraInstance))

        self.instances = tuple(instances)

        frames_count = br.read_uint16()
        if frames_count > 0:
            flags = 0xFF
            if version != 0:
                flags = br.read_uint8()

            self.frames = br.read_struct(ScwFrame, frames_count, flags=flags)
