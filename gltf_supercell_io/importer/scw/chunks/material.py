from . import ScwChunk, BinaryReader, BrStruct
from dataclasses import dataclass, field
from typing import Optional, cast
from enum import IntFlag


class ShaderDefine(IntFlag):
    DEFAULT = 0
    AMBIENT = 0x00001
    DIFFUSE = 0x00002
    STENCIL = 0x00004
    COLORIZE = 0x00008
    EMISSION = 0x00010
    OPACITY = 0x00020
    LIGHTMAP = 0x00040
    SPECULAR = 0x00080

    COLORTRANSFORM_MUL = 0x00100
    COLORTRANSFORM_ADD = 0x00200

    SHADOWMAP = 0x00400
    CUTOUT = 0x00800
    NORMAL = 0x01000
    VERTEX_COLOR = 0x02000
    BAKED_LIGHTMAP = 0x04000
    CLIP_PLANE = 0x08000
    COLOR_GRADING = 0x10000
    SSS = 0x20000

    @classmethod
    def from_int(cls, flags: int) -> "ShaderDefine":
        return cls(flags)

    @property
    def as_int(self) -> int:
        return int(self)

    @property
    def as_list(self) -> list[str]:
        return [cast(str, flag.name) for flag in type(self) if self & flag]

    def has(self, flag: "ShaderDefine") -> bool:
        return bool(self & flag)

    def enable(self, flag: "ShaderDefine") -> "ShaderDefine":
        return self | flag

    def disable(self, flag: "ShaderDefine") -> "ShaderDefine":
        return self & ~flag

    def toggle(self, flag: "ShaderDefine") -> "ShaderDefine":
        return self ^ flag


@dataclass
class Color(BrStruct):
    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        self.a, self.b, self.g, self.r = tuple([val / 0xFF for val in br.read_uint8(4)])

    @property
    def values(self):
        return [self.r, self.g, self.b, self.a]


@dataclass
class Texture(BrStruct):
    surface: str | Color = field(default_factory=Color)

    def __br_read__(self, br: "BinaryReader", *args, **kwargs):
        use_texture = br.read_bool()
        if use_texture:
            self.surface = br.read_str() or ""
        else:
            self.surface = br.read_struct(Color)


@dataclass
class ScwMaterial(ScwChunk):
    name = ""
    shader = ""
    blend_mode = 4

    ambient: Color = field(default_factory=Color)

    diffuse: Texture = field(default_factory=Texture)
    specular: Texture = field(default_factory=Texture)

    stencil_tex: Optional[str] = None
    normal_tex: Optional[str] = None

    colorize: Texture = field(default_factory=Texture)
    emission: Texture = field(default_factory=Texture)

    opacity_tex: Optional[str] = None
    opacity: float = 1.0

    cutout: float = 0.0

    diffuse_lightmap: Optional[str] = None
    specular_lightmap: Optional[str] = None

    baked_lightmap: Optional[str] = None
    clip_plane: Color = field(default_factory=Color)
    shader_define: ShaderDefine = ShaderDefine.DEFAULT

    def __br_read__(self, br: "BinaryReader", version=-1, *args, **kwargs):
        self.name = br.read_str() or ""
        self.shader = br.read_str() or ""
        self.blend_mode = br.read_uint8()
        br.read_uint8()
        self.ambient = br.read_struct(Color)
        self.diffuse = br.read_struct(Texture)
        self.specular = br.read_struct(Texture)
        self.stencil_tex = br.read_str()

        if version > 0:
            self.normal_tex = br.read_str()

        self.colorize = br.read_struct(Texture)
        self.emission = br.read_struct(Texture)
        self.opacity_tex = br.read_str()
        self.opacity = br.read_float()
        self.cutout = br.read_float()
        self.diffuse_lightmap = br.read_str()
        self.specular_lightmap = br.read_str()

        if version >= 2:
            self.baked_lightmap = br.read_str()

        self.shader_define = ShaderDefine(br.read_uint32())
        if self.shader_define.has(ShaderDefine.CLIP_PLANE):
            self.clip_plane = br.read_struct(Color)
