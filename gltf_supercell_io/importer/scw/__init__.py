from ...com.utilities.binary_reader import BinaryReader, Endian
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.io.imp.gltf2_io_gltf import ImportError
from .chunks import ScwChunk
from .chunks.header import ScwHeader
from .chunks.geometry import ScwGeometry
from .chunks.nodes import ScwNodes
from os.path import isfile
from typing import cast
from io_scene_gltf2.io.com.gltf2_io import Gltf, Node
from ...com import glTF_material_extension_name

CHUNKS: list[type[ScwChunk]] = [ScwHeader]


class ScwFile:
    def __init__(self, filename: str, settings: dict) -> None:
        self.filename = filename
        self.gltf = glTFImporter(filename, settings)
        self.version = -1

    def _import_header(self, header: ScwHeader):
        self.version = header.version

    def _import_mesh(self, mesh: ScwGeometry):
        pass

    def _import_nodes(self, nodes: ScwNodes):
        gltf_nodes = [
            Node(
                camera=None,
                children=[],
                extensions=None,
                extras=None,
                matrix=None,
                mesh=None,
                name=node.name,
                rotation=None,
                scale=None,
                translation=None,
                weights=None,
                skin=None,
            )
            for node in nodes.nodes
        ]

        def gather_children(name: str):
            result: list[int] = []
            for i, node in enumerate(nodes.nodes):
                if node.parent == name:
                    result.append(i)

            return result

        for idx in range(len(nodes.nodes)):
            gltf_node = gltf_nodes[idx]
            node = nodes.nodes[idx]

            # Converting parent-based tree to child-based tree
            gltf_node.children = gather_children(cast(str, node.name))

            # Processing node bind transformation
            if len(node.frames) > 0:
                frame = node.frames[0]
                gltf_node.translation = [val or 0.0 for val in frame.translation.values]  # type: ignore
                if frame.rotation is not None:
                    gltf_node.rotation = list(frame.rotation)  # type: ignore

                gltf_node.scale = [val or 1.0 for val in frame.scale.values]  # type: ignore

        self.gltf.data.nodes = gltf_nodes

    def _read_chunks(self, data: BinaryReader):
        while True:
            length = data.read_int32()
            signature = data.read_bytes(4)
            position = data.pos()
            if 0 > length:
                # raise ImportError("SCW Chunk has negative length")
                continue

            match signature:
                case b"HEAD":
                    chunk = data.read_struct(ScwHeader)
                    self._import_header(chunk)

                case b"GEOM":
                    chunk = data.read_struct(ScwGeometry, version=self.version)
                    self._import_mesh(chunk)

                case b"NODE":
                    chunk = data.read_struct(ScwNodes)
                    self._import_nodes(chunk)

                case b"WEND":
                    return

                case _:
                    self.gltf.log.warning(
                        f"Unknown SCW chunk {signature.decode("ascii")}"
                    )

            data.seek(position + length + 4)

    def read(self):
        if not isfile(self.filename):
            raise ImportError("Please select a file")

        with open(self.filename, "rb") as f:
            content = memoryview(f.read())

        data = BinaryReader(content, Endian.BIG)
        if data.read_bytes(4) != b"SC3D":
            raise ImportError("Invalid Supercell World file")

        self.gltf.data = Gltf(
            accessors=[],
            animations=[],
            asset=None,
            buffers=[],
            buffer_views=[],
            cameras=[],
            extensions=None,
            extensions_required=[],
            extensions_used=[glTF_material_extension_name],
            extras=None,
            images=[],
            materials=[],
            meshes=[],
            nodes=[],
            samplers=[],
            scene=None,
            scenes=[],
            skins=[],
            textures=[],
        )
        self._read_chunks(data)
