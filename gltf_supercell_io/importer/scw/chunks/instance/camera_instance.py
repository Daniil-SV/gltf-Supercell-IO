from dataclasses import dataclass

from . import BinaryReader, ScwInstance


@dataclass
class ScwCameraInstance(ScwInstance):
    camera_name: str = ""
    target: str = ""

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.camera_name = br.read_str() or ""
        self.target = br.read_str() or ""
