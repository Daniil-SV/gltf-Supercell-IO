from .builder import ShaderBuilder


class BrawlStarsLegacy(ShaderBuilder):
    CONSTANT_MAP = {
        0: "AMBIENT",
        2: "DIFFUSE",
        4: "SPECULAR",
        7: "COLORIZE",
        9: "LIGHTMAP",
        12: "OPACITY",
        14: "EMISSION",
        16: "STENCIL",
        20: "CLIP_PLANE",
        22: "COLORTRANSFORM_ADD",  # Not sure about that, but it was smth like that
        24: "COLORTRANSFORM_MUL"
    }

    COLOR_MAP = {
        1: "ambient",
        3: "diffuse",
        6: "specular",
        8: "colorize",
        10: "lightmap",
        11: "lightmapSpecular",
        15: "emission",
        21: "clipPlane"
    }

    TEXTURE_MAP = {
        13: "opacityTex2D"
    }

    def create_shader(self):
        self.shader = self.instantiate_shader(
            "ScLegacyBrawlStarsShader", "Brawl Stars Legacy Shader")

        for idx, key in BrawlStarsLegacy.CONSTANT_MAP.items():
            self.set_constant_prop(key, idx)

        for idx, key in BrawlStarsLegacy.COLOR_MAP.items():
            self.set_color_prop(key, idx)

        for idx, key in BrawlStarsLegacy.COLOR_MAP.items():
            self.set_texture_prop(f"{key}Tex2D", idx)

        for idx, key in BrawlStarsLegacy.TEXTURE_MAP.items():
            self.set_texture_prop(key, idx)

        self.set_bool_prop("enableStencilTex", 17)
        self.set_texture_prop("stencilTex2D", 18)
        self.set_texture_prop("opacityTex2D", 13)
        self.set_float_prop("opacity", 13)
