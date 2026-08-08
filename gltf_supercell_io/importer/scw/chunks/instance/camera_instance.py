from . import ScwInstance, BinaryReader


class ScwCameraInstance(ScwInstance):
    camera_name = ""
    target = ""

    def __br_read__(self, br: "BinaryReader"):
        self.camera_name = br.read_str()
        self.target = br.read_str()
