from dataclasses import dataclass, field

from io_scene_gltf2.io.com.gltf2_io import Accessor, Node

from .animation_flags import OdinAnimationFlags

ROTATION_CHANNELS = 4
TRANSLATION_CHANNELS = 3
SCALE_CHANNELS = 3


@dataclass
class AnimationNode:
    # Total size of deltas written in dataAccessor
    dataSize: int

    # Setting specifies available animation channels
    flags: OdinAnimationFlags

    # Count of animation frames
    frameCount: int

    # Reference to animation node
    nodeIndex: Node


@dataclass
class PackedAnimationDescriptor:
    # Accessor containing quaternion compressed data
    uintAccessor: Accessor

    # Accessor with node's base transform (trs)
    nodeAccessor: Accessor

    # Main accessor with written deltas for each channel and node transforms
    dataAccessor: Accessor

    # Single decoded frame size
    stride: int

    # An array of packed frames for each node
    nodes: list[AnimationNode] = field(default_factory=list)


@dataclass
class Animation:
    # Animation first frame
    firstFrame: float

    # Animation last frame
    lastFrame: float

    # Animation frame rate
    frameRate: float

    # Total keyframes count
    keyframeCount: int

    # Packed frames
    packed: PackedAnimationDescriptor
