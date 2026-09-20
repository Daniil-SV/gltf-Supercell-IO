from math import ceil, floor, sqrt
from typing import TYPE_CHECKING

import bpy
import numpy as np
from io_scene_gltf2.blender.exp.accessors import array_to_accessor
from io_scene_gltf2.io.com.constants import ComponentType, DataType
from io_scene_gltf2.io.com.gltf2_io import Animation, Node

from ...com import glTF_extension_name
from ...com.odin.animation import (
    ROTATION_CHANNELS,
    SCALE_CHANNELS,
    TRANSLATION_CHANNELS,
    PackedAnimationDescriptor,
)
from ...com.odin.animation import (
    Animation as OdinAnimation,
)
from ...com.odin.animation import (
    AnimationNode as OdinAnimationNode,
)
from ...com.odin.animation_flags import OdinAnimationFlags
from .component import glTF2BaseExporterComponent, requires_odin, to_dict

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import (
        Accessor,
        AnimationChannel,
        AnimationChannelTarget,
        AnimationSampler,
    )

TRANSLATION = "translation"
ROTATION = "rotation"
SCALE = "scale"
CHANNELS = [TRANSLATION, ROTATION, SCALE]

EPSILON = 0.0001
UNPACK_SCALE = 1.0 / 32767.0


def nearly_equal(a: float, b: float):
    return abs(a - b) < EPSILON


def quaternion_dot(a: np.ndarray, b: np.ndarray):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]


def same_quaternion(a: np.ndarray, b: np.ndarray):
    if quaternion_dot(a, b) >= 0.0:
        return (
            nearly_equal(a[0], b[0])
            and nearly_equal(a[1], b[1])
            and nearly_equal(a[2], b[2])
            and nearly_equal(a[3], b[3])
        )

    return (
        nearly_equal(a[0], -b[0])
        and nearly_equal(a[1], -b[1])
        and nearly_equal(a[2], -b[2])
        and nearly_equal(a[3], -b[3])
    )


def pack_unit(value: float) -> int:
    return max(-32767, min(32767, floor(value * 32767.0 + 0.5)))


def pack_delta(value: float, base: float, scale: float) -> int:
    if abs(scale) < 1e-12:
        return 0
    scaled = (value - base) / scale
    rounded = floor(scaled + 0.5) if scaled >= 0 else ceil(scaled - 0.5)
    return max(-32767, min(32767, rounded))


class PackedFrames:
    FRAME_TIME = "f"
    TRANSLATION = "t"
    TRANSLATION_MULTIPLIER = "tm"
    ROTATION = "r"
    SCALE = "s"
    SCALE_MULTIPLIER = "sm"

    NODE_BUFFER_DTYPE = np.dtype(
        [
            (TRANSLATION, np.float32, (TRANSLATION_CHANNELS,)),
            (SCALE, np.float32, (SCALE_CHANNELS,)),
            (TRANSLATION_MULTIPLIER, np.float32),
            (SCALE_MULTIPLIER, np.float32),
        ]
    )

    UNIT_BUFFER_DTYPE = np.dtype([(ROTATION, np.uint16, (ROTATION_CHANNELS,))])

    def __init__(self, node: "Node", flags: OdinAnimationFlags, count=0) -> None:
        if 0 >= count:
            raise Exception("Odin animation required to have at least one frame")

        self.node = node
        self.frame_count = count
        self.flags = flags
        self.data: np.ndarray = None  # type: ignore

        self.nodes: np.ndarray = np.zeros(1, dtype=self.NODE_BUFFER_DTYPE)[0]
        self.units: np.ndarray = np.zeros(1, dtype=self.UNIT_BUFFER_DTYPE)[0]

    def set_base(
        self,
        translation: np.ndarray | None,
        rotation: np.ndarray | None,
        scale: np.ndarray | None,
        scale_multiplier: float,
        translation_multiplier: float,
    ):
        if translation is not None:
            self.nodes[self.TRANSLATION] = translation.astype(np.float32)

        if rotation is not None:
            self.units[self.ROTATION] = rotation.astype(np.float32)

        if scale is not None:
            self.nodes[self.SCALE] = scale.astype(np.float32)
        else:
            self.nodes[self.SCALE] = np.array([1.0, 1.0, 1.0], dtype=np.float32)

        self.nodes[self.SCALE_MULTIPLIER] = max(
            scale_multiplier, EPSILON * UNPACK_SCALE
        )
        self.nodes[self.TRANSLATION_MULTIPLIER] = max(
            translation_multiplier, EPSILON * UNPACK_SCALE
        )

    def set_scale(self, target: np.ndarray, source: np.ndarray):
        base = self.nodes[self.SCALE]

        scale = self.nodes[self.SCALE_MULTIPLIER]
        target[self.SCALE][0] = pack_delta(source[0], base[0], float(scale))
        if self.flags.has_scale3D:
            target[self.SCALE][1] = pack_delta(source[1], base[1], float(scale))
            target[self.SCALE][2] = pack_delta(source[2], base[2], float(scale))

    @property
    def stride(self):
        result = 0

        if self.flags.has_tracktime:
            result += 1

        if self.flags.has_rotation:
            result += 4

        if self.flags.has_translation:
            result += 3

        if self.flags.has_scale:
            if self.flags.has_scale3D:
                result += 3
            else:
                result += 1

        return result


def decode_accessor(accessor: "Accessor"):
    dtype = ComponentType.to_numpy_dtype(accessor.component_type)
    component_nb = DataType.num_elements(accessor.type)
    num_elems = accessor.count * component_nb
    array = np.frombuffer(
        accessor.buffer_view.data,
        dtype=np.dtype(dtype).newbyteorder("<"),
        count=num_elems,
    ).reshape(accessor.count, component_nb)
    return array


class AnimationExporter(glTF2BaseExporterComponent):
    def pre_export_hook(self, export_settings):
        if not export_settings["gltf_force_sampling"]:
            print(
                "Odin requires force sampling for proper node animations. Enabling animating sampling back..."
            )
            export_settings["gltf_force_sampling"] = True

        export_settings["gltf_sampling_interpolation_fallback"] = "STEP"

    def convert_frames(self, node: "Node", channels: dict[str, "AnimationSampler"]):
        flags = OdinAnimationFlags()

        source: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for path, channel in channels.items():
            timestamps: Accessor = channel.input
            output: Accessor = channel.output

            timestamps_data = decode_accessor(timestamps)
            output_data = decode_accessor(output)
            if 0 >= timestamps_data.shape[0] or 0 >= output_data.shape[0]:
                continue

            source[path] = (timestamps_data, output_data)

        # Preparing flags and base node values
        frame_start = min([timestamps.min() for timestamps, _ in source.values()])
        frame_end = min([timestamps.max() for timestamps, _ in source.values()])

        translation_timestamp, translation = source.get(TRANSLATION, (None, None))
        translation_count = (
            0 if translation_timestamp is None else translation_timestamp.shape[0]
        )

        rotation_timestamp, rotation = source.get(ROTATION, (None, None))
        rotation_count = (
            0 if rotation_timestamp is None else rotation_timestamp.shape[0]
        )

        scale_timestamp, scale = source.get(SCALE, (None, None))
        scale_count = 0 if scale_timestamp is None else scale_timestamp.shape[0]

        frame_count = max(translation_count, rotation_count, scale_count)

        init_translation = None if translation is None else translation[0]
        init_rotation = None if rotation is None else rotation[0]
        init_scale = None if scale is None else scale[0]

        # TODO?: I could add frame time use to optimize even more but uhh...

        # Determine frame flags
        for f in range(1, frame_count):
            # Rotation
            if (
                rotation is not None
                and init_rotation is not None
                and rotation_count > f
            ):
                frame_rotation = rotation[f]
                if not same_quaternion(frame_rotation, init_rotation):
                    flags = OdinAnimationFlags.withRotation(flags)

            # Translation
            if (
                translation is not None
                and init_translation is not None
                and translation_count > f
            ):
                frame_translation = translation[f]
                if False in [
                    nearly_equal(frame_translation[i], init_translation[i])
                    for i in range(TRANSLATION_CHANNELS)
                ]:
                    flags = OdinAnimationFlags.withTranslation(flags)

            # Scale
            if scale is not None and init_scale is not None and scale_count > f:
                frame_scale = scale[f]
                if False in [
                    nearly_equal(frame_scale[i], init_scale[i])
                    for i in range(SCALE_CHANNELS)
                ]:
                    flags = OdinAnimationFlags.withScale(flags)

                if not nearly_equal(frame_scale[0], frame_scale[1]) or not nearly_equal(
                    frame_scale[0], frame_scale[2]
                ):
                    flags = OdinAnimationFlags.withScale3D(flags)

        if flags == 0:
            # It seems that this node is static
            # We could just assign base animation values to node's properties
            if init_translation is not None:
                node.translation = [
                    float(init_translation[i]) for i in range(TRANSLATION_CHANNELS)
                ]
            else:
                node.translation = None

            if init_rotation is not None:
                node.rotation = [
                    float(init_rotation[i]) for i in range(ROTATION_CHANNELS)
                ]
            else:
                node.rotation = None

            if init_scale is not None:
                node.scale = [float(init_scale[i]) for i in range(SCALE_CHANNELS)]
            else:
                node.scale = None

            return

        # Create RLE block mapping
        rle_blocks: list[int] = []
        rle_length = 1  # First frame is literal frame
        last_frame: tuple[np.ndarray, ...] = (init_translation, init_rotation, init_scale)  # type: ignore
        for f in range(1, frame_count):
            is_literal_frame = False

            base_translation, base_rotation, base_scale = last_frame
            frame_translation = None
            frame_rotation = None
            frame_scale = None

            # Translation
            if (
                flags.has_translation
                and translation is not None
                and translation_count > f
            ):
                frame_translation = translation[f]
                if False in [
                    nearly_equal(frame_translation[i], base_translation[i])
                    for i in range(TRANSLATION_CHANNELS)
                ]:
                    is_literal_frame = True

            # Rotation
            if flags.has_rotation and rotation is not None and rotation_count > f:
                frame_rotation = rotation[f]
                if not same_quaternion(frame_rotation, base_rotation):
                    is_literal_frame = True

            # Scale
            if flags.has_scale and scale is not None and scale_count > f:
                frame_scale = scale[f]
                if flags.has_scale3D:
                    if False in [
                        nearly_equal(frame_scale[i], base_scale[i])
                        for i in range(SCALE_CHANNELS)
                    ]:
                        is_literal_frame = True
                else:
                    if not nearly_equal(frame_scale[0], base_scale[0]):
                        is_literal_frame = True

            is_literal_stream = rle_length > 0
            if is_literal_frame != is_literal_stream or rle_length >= 32767:
                rle_blocks.append(rle_length)
                rle_length = 0

            if is_literal_frame:
                rle_length += 1
            else:
                rle_length -= 1

            last_frame = (frame_translation, frame_rotation, frame_scale)  # type: ignore

        if rle_length != 0:
            rle_blocks.append(rle_length)

        if not rle_blocks:
            return

        # Calculating delta multipliers
        maximum_translation_delta = 0.0
        maximum_scale_delta = 0.0
        for f in range(1, frame_count):
            if flags.has_translation and translation_count > f:
                frame_translation = translation[f]  # type: ignore
                maximum_translation_delta = max(
                    [maximum_translation_delta]
                    + [
                        abs(frame_translation[i] - init_translation[i])  # type: ignore
                        for i in range(TRANSLATION_CHANNELS)
                    ]
                )

            if flags.has_scale and scale_count > f:
                frame_scale = scale[f]  # type: ignore
                maximum_scale_delta = max(
                    maximum_scale_delta, abs(frame_scale[0] - init_scale[0])  # type: ignore
                )
                if flags.has_scale3D:
                    maximum_scale_delta = max(
                        maximum_scale_delta,
                        abs(frame_scale[1] - init_scale[1]),  # type: ignore
                        abs(frame_scale[2] - init_scale[2]),  # type: ignore
                    )

        if flags.has_scale3D and not flags.has_scale:
            flags = OdinAnimationFlags(flags & ~0x18)

        packed = PackedFrames(node, flags, frame_count)
        packed.set_base(
            init_translation,
            init_rotation,
            init_scale,
            max(maximum_scale_delta, EPSILON) * UNPACK_SCALE,
            max(maximum_translation_delta, EPSILON) * UNPACK_SCALE,
        )

        # Packing frames
        frame_index = 0
        rle_block_idx = 0

        data_buffer_count = sum(
            [block * packed.stride for block in rle_blocks if block > 0]
        ) + len(rle_blocks)
        data_buffer = np.zeros((data_buffer_count,), dtype=np.int16)
        data_offset = 0

        def write(value: int):
            nonlocal data_offset
            data_buffer[data_offset] = value
            data_offset += 1

        def write_rotation(source: np.ndarray):
            # Normalize rotation
            x, y, z, w = source
            length_sq = x * x + y * y + z * z + w * w
            if length_sq < 1e-12:
                for _ in range(ROTATION_CHANNELS):
                    write(0)
                return
            length = 1.0 / sqrt(length_sq)
            for i in range(ROTATION_CHANNELS):
                write(pack_unit(source[i] * length))

        def write_translation(source: np.ndarray):
            base = packed.nodes[PackedFrames.TRANSLATION]

            for i in range(TRANSLATION_CHANNELS):
                write(
                    pack_delta(
                        source[i],
                        base[i],
                        float(packed.nodes[PackedFrames.TRANSLATION_MULTIPLIER]),
                    )
                )

        def write_scale(source: np.ndarray):
            base = packed.nodes[PackedFrames.SCALE]

            scale = packed.nodes[PackedFrames.SCALE_MULTIPLIER]
            write(pack_delta(source[0], base[0], float(scale)))
            if packed.flags.has_scale3D:
                write(pack_delta(source[1], base[1], float(scale)))
                write(pack_delta(source[2], base[2], float(scale)))

        last_frame: tuple[np.ndarray, ...] = (init_translation, init_rotation, init_scale)  # type: ignore
        while packed.frame_count > frame_index:
            rle_length = rle_blocks[rle_block_idx]
            write(rle_length)

            if rle_length > 0:
                for _ in range(rle_length):
                    last_translation, last_rotation, last_scale = last_frame

                    # Rotation
                    if packed.flags.has_rotation and rotation_count > frame_index:
                        frame_rotation = rotation[frame_index]  # type: ignore
                        last_rotation = frame_rotation

                        write_rotation(frame_rotation)
                    elif packed.flags.has_rotation:
                        frame_rotation = last_rotation
                        write_rotation(last_rotation)
                    else:
                        frame_rotation = None

                    # Translation
                    if packed.flags.has_translation and translation_count > frame_index:
                        frame_translation = translation[frame_index]  # type: ignore
                        last_translation = frame_translation

                        write_translation(frame_translation)
                    elif packed.flags.has_translation:
                        frame_translation = last_translation
                        write_translation(last_translation)
                    else:
                        frame_translation = None

                    # Scale
                    if packed.flags.has_scale and scale_count > frame_index:
                        frame_scale = scale[frame_index]  # type: ignore
                        last_scale = frame_scale

                        write_scale(frame_scale)
                    elif packed.flags.has_scale:
                        frame_scale = last_scale
                        write_scale(last_scale)
                    else:
                        frame_scale = None

                    last_frame = (frame_translation, frame_rotation, frame_scale)  # type: ignore
                    frame_index += 1
            else:
                frame_index += -rle_length

            rle_block_idx += 1

        packed.data = data_buffer
        return float(frame_start), float(frame_end), packed

    def convert_animation(
        self,
        animation: "Animation",
        node_refs: dict[int, "Node"],
        nodes: dict[int, dict[str, "AnimationSampler"]],
    ):
        # Gathering node channels
        channels: list[AnimationChannel] = animation.channels
        for channel in channels:
            target: AnimationChannelTarget = channel.target

            if target is None or target.node is None:
                print(f"Animation target is invalid {target} / {target.path}. Skip...")
                continue

            if target.path not in CHANNELS:
                print(
                    f"Animation node {target.node.name} already has animation path {target.path}."
                    "Possible that the scene is being exported with multiple animations, which is not supported by Odin."
                )
                continue

            # Getting node reference id
            key = id(target.node)
            node_refs.setdefault(key, target.node)
            node_channels = nodes.setdefault(key, {})
            sampler: AnimationSampler = animation.samplers[channel.sampler]

            node_channels[target.path] = sampler

    @requires_odin
    def gather_gltf_hook(self, active_scene_idx, scenes, animations, export_settings):
        node_refs: dict[int, Node] = {}
        nodes: dict[int, dict[str, AnimationSampler]] = {}

        # Extracting every channel from every animation of glb
        for animation in animations:
            self.convert_animation(animation, node_refs, nodes)

        # Basic settings
        frame_start = 0.0
        frame_end = 0.0

        fps = 30.0
        if bpy.context.scene:
            fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base

        # Prepare packed nodes
        packed_frames: list[PackedFrames] = []
        for node_id, node_channels in nodes.items():
            if not node_channels:
                continue

            node: Node = node_refs[node_id]
            frames = self.convert_frames(node, node_channels)
            if frames is None:
                continue

            start, end, node_packed = frames
            frame_start = min(frame_start, start)
            frame_end = max(frame_end, end)

            if node_packed.data is None:
                continue

            packed_frames.append(node_packed)

        if not packed_frames:
            return

        unitBuffer = (
            np.array(
                [packed.units for packed in packed_frames],
                dtype=PackedFrames.UNIT_BUFFER_DTYPE,
            )
            .view(np.uint16)
            .flatten()
        )
        unitAccessor = array_to_accessor(
            "", unitBuffer, export_settings, ComponentType.Short, DataType.Scalar
        )
        unitAccessor.component_type |= 0x30000

        nodeBuffer = (
            np.array(
                [packed.nodes for packed in packed_frames],
                dtype=PackedFrames.NODE_BUFFER_DTYPE,
            )
            .view(np.float32)
            .flatten()
        )
        nodeAccessor = array_to_accessor(
            "", nodeBuffer, export_settings, ComponentType.Float, DataType.Scalar
        )
        nodeAccessor.component_type |= 0x20000

        dataBuffer = np.concatenate([packed.data for packed in packed_frames])
        dataAccessor = array_to_accessor(
            "", dataBuffer, export_settings, ComponentType.Short, DataType.Scalar
        )
        dataAccessor.component_type |= 0x10000

        stride = sum([packed.stride for packed in packed_frames])
        descriptor = PackedAnimationDescriptor(
            unitAccessor,
            nodeAccessor,
            dataAccessor,
            stride,
            [
                OdinAnimationNode(
                    packed.data.size,
                    packed.flags,
                    packed.frame_count,
                    packed.node,
                )
                for packed in packed_frames
            ],
        )

        animation = OdinAnimation(
            round(frame_start * fps, 2),
            round(frame_end * fps, 2),
            fps,
            max([packed.frame_count for packed in packed_frames]),
            descriptor,
        )

        # Trick: Create proxy animation so buffer finalize could pickup our
        # animations accessors and include it to gltf successfully
        animations.clear()
        animations.append(
            Animation(None, {glTF_extension_name: to_dict(animation)}, None, None, None)
        )

    @requires_odin
    def gather_gltf_extensions_hook(self, gltf, export_settings):
        if gltf.extensions is None:
            gltf.extensions = {}

        if glTF_extension_name not in gltf.extensions:
            gltf.extensions[glTF_extension_name] = {}

        # Searching for proxy animations
        for animation in gltf.animations:
            if glTF_extension_name in animation.extensions:
                gltf.extensions[glTF_extension_name]["animation"] = (
                    animation.extensions[glTF_extension_name]
                )
                break

        gltf.animations = []
