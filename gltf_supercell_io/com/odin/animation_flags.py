class OdinAnimationFlags(int):
    def __new__(cls, flags: int = 0):
        return super().__new__(cls, flags)

    def __get_flag(self, idx: int) -> bool:
        return self.flags & (1 << idx) != 0

    @staticmethod
    def __withFlag(flags: int, idx: int):
        return OdinAnimationFlags(flags | (1 << idx))

    @property
    def flags(self) -> int:
        return int(self)

    @property
    def has_transform(self) -> bool:
        return self.flags != 0

    @property
    def has_tracktime(self) -> bool:
        return self.__get_flag(0)

    @staticmethod
    def withTracktime(flags: int = 0):
        return OdinAnimationFlags.__withFlag(flags, 0)

    @property
    def has_rotation(self) -> bool:
        return self.__get_flag(1)

    @staticmethod
    def withRotation(flags: int = 0):
        return OdinAnimationFlags.__withFlag(flags, 1)

    @property
    def has_translation(self) -> bool:
        return self.__get_flag(2)

    @staticmethod
    def withTranslation(flags: int = 0):
        return OdinAnimationFlags.__withFlag(flags, 2)

    @property
    def has_scale3D(self) -> bool:
        return self.__get_flag(4)

    @staticmethod
    def withScale3D(flags: int = 0):
        return OdinAnimationFlags.__withFlag(flags, 4)

    @property
    def has_scale(self) -> bool:
        return self.__get_flag(3)

    @staticmethod
    def withScale(flags: int = 0):
        return OdinAnimationFlags.__withFlag(flags, 3)

    @property
    def elements_count(self) -> int:
        counter = 0
        if self.has_tracktime:
            counter += 1
        if self.has_rotation:
            counter += 4
        if self.has_translation:
            counter += 3
        if self.has_scale and self.has_scale3D:
            counter += 3
        elif self.has_scale3D:
            counter += 1

        return counter
