"""
Patches for glTF exporter animation keyframe gathering.

The Supercell importer stores the original SC pose scale (e.g. ``1.84``) in the
``scScaleOverride`` custom property on each affected pose bone, and divides
the keyframed scale values during animation import so that Blender's rest pose
has unit scale (otherwise the armature modifier would deform the mesh at
rest). On export those divided values (``1.0``) are read from Blender, which
loses the absolute SC scale and breaks the file for viewers that honor
standard glTF animation (BabylonJS, the SC game engine).

These patches wrap the two keyframe-gathering entry points used by the glTF
exporter -- sampled bone keyframes and FCurve keyframes -- and multiply every
``scale`` keyframe value (including cubic-spline tangents) by the bone's ``scScaleOverride``
"""

import bpy
from typing import Optional, Tuple

from ...com.utilities.patcher import Patch

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _componentwise_mul(value, factors):
    result = []
    for i, v in enumerate(value):
        result.append(v * factors[i])
    return result


def _get_scale_override_from_pose_bone(armature, bone_name):
    pb = armature.pose.bones.get(bone_name)
    if pb is None:
        return None
    sco = pb.get("scScaleOverride")
    if sco is None:
        return None
    sx, sy, sz = sco
    if sx == 1.0 and sy == 1.0 and sz == 1.0:
        return None
    return (sx, sy, sz)


def _apply_scale_override_to_keyframes(keyframes, factors):
    """Multiply each scale keyframe value and tangents by ``factors``.

    ``Keyframe.value``/``in_tangent``/``out_tangent`` use Blender's coordinate
    system (Z-up). The exporter applies the Y-up swizzle later, so we scale
    in Blender space here.
    """
    factors3 = factors
    for kf in keyframes:
        if kf.target != "scale":
            continue

        # value (Vector or list): use the indexed setters so the value
        # array is replaced in place.
        if kf.value is not None:
            new_value = _componentwise_mul(kf.value, factors3)
            kf.value_total = new_value  # bypass indexed setter

        # Tangents: only relevant for CUBICSPLINE.
        if kf.in_tangent is not None:
            orig = list(kf.in_tangent)
            for i in range(3):
                kf.set_value_index_in(i, orig[i] * factors3[i])

        if kf.out_tangent is not None:
            orig = list(kf.out_tangent)
            for i in range(3):
                kf.set_value_index_out(i, orig[i] * factors3[i])


# Capture the originals before patching. We rely on the io_scene_gltf2
# addon being already loaded at the time this SC addon is registered.
from io_scene_gltf2.blender.exp.animation.sampled.armature.keyframes import (  # noqa: E402
    gather_bone_sampled_keyframes as _orig_sampled_armature_keyframes,
)
from io_scene_gltf2.blender.exp.animation.fcurves.keyframes import (  # noqa: E402
    gather_fcurve_keyframes as _orig_fcurve_keyframes,
)


def _patched_sampled_armature_keyframes(
    armature_uuid: str,
    bone: str,
    channel: str,
    action_name: str,
    slot_identifier: str,
    node_channel_is_animated: bool,
    export_settings,
):
    props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore
    keyframes = _orig_sampled_armature_keyframes(
        armature_uuid,
        bone,
        channel,
        action_name,
        slot_identifier,
        node_channel_is_animated,
        export_settings,
    )
    if not props.enabled:
        return keyframes

    if keyframes is None or channel != "scale":
        return keyframes

    armature = export_settings["vtree"].nodes[armature_uuid].blender_object
    sco = _get_scale_override_from_pose_bone(armature, bone)
    if sco is None:
        return keyframes

    _apply_scale_override_to_keyframes(keyframes, sco)
    return keyframes


def _patched_fcurve_keyframes(
    obj_uuid: str,
    channel_group: Tuple,
    bone: Optional[str],
    custom_range: Optional[set],
    extra_mode: bool,
    export_settings,
):
    props = bpy.context.scene.glTFSupercellExporterProperties  # type: ignore
    keyframes = _orig_fcurve_keyframes(
        obj_uuid, channel_group, bone, custom_range, extra_mode, export_settings
    )
    if not props.enabled:
        return keyframes
    if keyframes is None or len(keyframes) == 0:
        return keyframes
    if keyframes[0].target != "scale" or bone is None:
        return keyframes

    vnode = export_settings["vtree"].nodes.get(obj_uuid)
    if (
        vnode is None
        or vnode.blender_object is None
        or vnode.blender_object.type != "ARMATURE"
    ):
        return keyframes

    sco = _get_scale_override_from_pose_bone(vnode.blender_object, bone)
    if sco is None:
        return keyframes

    _apply_scale_override_to_keyframes(keyframes, sco)
    return keyframes


sampled_armature_keyframes_patch = Patch(
    "sampled armature keyframes scale override",
    module_path="io_scene_gltf2.blender.exp.animation.sampled.armature.keyframes",
    target_method="gather_bone_sampled_keyframes",
    function=_patched_sampled_armature_keyframes,
)

fcurve_keyframes_patch = Patch(
    "fcurve keyframes scale override",
    module_path="io_scene_gltf2.blender.exp.animation.fcurves.keyframes",
    target_method="gather_fcurve_keyframes",
    function=_patched_fcurve_keyframes,
)
