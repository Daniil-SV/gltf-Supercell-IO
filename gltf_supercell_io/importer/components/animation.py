import bpy
from mathutils import Vector
from typing import TYPE_CHECKING, Dict, Any

from .component import glTF2BaseImporterComponent
from ...com.animation.reader import OdinAnimationReader
from ...com.animation import OdinAnimation
from ...com import glTF_extension_name
from ...com.animation.packedReader import (
    TranslationChannels,
    ScaleChannels,
    RotationChannels,
)

from io_scene_gltf2.blender.imp.vnode import VNode
from io_scene_gltf2.blender.imp.animation_utils import (
    get_or_create_action_and_slot,
    make_fcurve,
)

if TYPE_CHECKING:
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
    from io_scene_gltf2.io.com.gltf2_io import Node


class OdinAnimationImporter(glTF2BaseImporterComponent):
    def do_animation_channel(
        self,
        animation: OdinAnimationReader,
        duration: int,
        fps: float,
        path: str,
        values: list,
        anim_idx: int,
        node_idx: int,
        gltf: "glTFImporter",
    ):
        vnodes: Dict[Any, VNode] = gltf.vnodes  # type: ignore
        vnode: VNode = vnodes[node_idx]  # type: ignore

        action, slot = get_or_create_action_and_slot(gltf, node_idx, anim_idx, path)

        num_components = 0
        blender_path = ""
        group_name = ""
        if path == "translation":
            blender_path = "location"
            group_name = "Object Transforms"
            num_components = 3
            values = [
                gltf.loc_gltf_to_blender(vals) for vals in values  # type: ignore #noqa
            ]
            values = vnode.base_locs_to_final_locs(values)

        elif path == "rotation":
            blender_path = "rotation_quaternion"
            group_name = "Object Transforms"
            num_components = 4
            values = [
                gltf.quaternion_gltf_to_blender(vals)  # type: ignore #noqa
                for vals in values
            ]
            values = vnode.base_rots_to_final_rots(values)

        elif path == "scale":
            blender_path = "scale"
            group_name = "Object Transforms"
            num_components = 3
            values = [
                gltf.scale_gltf_to_blender(vals)  # type: ignore #noqa
                for vals in values
            ]
            values = vnode.base_scales_to_final_scales(values)

        # Objects parented to a bone are translated to the bone tip by default.
        # Correct for this by translating backwards from the tip to the root.
        if vnode.type == VNode.Object and path == "translation":
            if vnode.parent is not None and vnodes[vnode.parent].type == VNode.Bone:
                bone_length = vnodes[vnode.parent].bone_length  # type: ignore
                off = Vector((0, -bone_length, 0))
                values = [vals + off for vals in values]

        if vnode.type == VNode.Bone:
            # Need to animate the pose bone when the node is a bone.
            group_name = vnode.blender_bone_name  # type: ignore
            blender_path = 'pose.bones["%s"].%s' % (
                bpy.utils.escape_identifier(vnode.blender_bone_name),  # type: ignore
                blender_path,
            )

            # We have the final TRS of the bone in values. We need to give
            # the TRS of the pose bone though, which is relative to the edit
            # bone.
            #
            #     Final = EditBone * PoseBone
            #   where
            #     Final =    Trans[ft] Rot[fr] Scale[fs]
            #     EditBone = Trans[et] Rot[er]
            #     PoseBone = Trans[pt] Rot[pr] Scale[ps]
            #
            # Solving for PoseBone gives
            #
            #     pt = Rot[er^{-1}] (ft - et)
            #     pr = er^{-1} fr
            #     ps = fs

            if path == "translation":
                edit_trans, edit_rot = vnode.editbone_trans, vnode.editbone_rot  # type: ignore
                edit_rot_inv = edit_rot.conjugated()
                values = [edit_rot_inv @ (trans - edit_trans) for trans in values]

            elif path == "rotation":
                edit_rot = vnode.editbone_rot  # type: ignore
                edit_rot_inv = edit_rot.conjugated()
                values = [edit_rot_inv @ rot for rot in values]

            elif path == "scale":
                pass  # no change needed

        # To ensure rotations always take the shortest path, we flip
        # adjacent antipodal quaternions.
        if path == "rotation":
            for i in range(1, len(values)):
                if values[i].dot(values[i - 1]) < 0:
                    values[i] = -values[i]

        fps = fps * bpy.context.scene.render.fps_base  # type: ignore

        coords = [0] * (2 * duration)
        coords[::2] = (  # type: ignore
            (animation.frame_spf * i) * fps for i in range(duration)  # type: ignore
        )

        for i in range(0, num_components):
            coords[1::2] = (vals[i] for vals in values)
            make_fcurve(
                action,
                slot,
                coords,
                data_path=blender_path,
                index=i,
                group_name=group_name,
            )

    def gather_import_animation_before_hook(self, anim_idx: int, gltf: "glTFImporter"):
        extensions = gltf.data.animations[anim_idx].extensions or {}
        descriptor = extensions.get(glTF_extension_name)
        if descriptor is None:
            return
        animation = OdinAnimation.Create(gltf, descriptor)

        fps = bpy.context.scene.render.fps  # type: ignore
        if self.properties.fps_source == "SEQUENCE":
            bpy.context.scene.render.fps = int(animation.frame_rate)  # type: ignore # noqa
            fps = animation.frame_rate
        elif self.properties.fps_source == "CUSTOM":
            fps = self.properties.fps_custom

        for i, node_idx in enumerate(animation.used_nodes):
            duration = animation.keyframe_count
            if animation.keyframe_mapping is not None:
                duration = animation.keyframe_mapping[i]
            translation = animation.get_translation(i)
            rotation = animation.get_rotation(i)
            scale = animation.get_scale(i)

            if translation is not None:
                translation = [
                    list(translation[c][f] for c in range(TranslationChannels))
                    for f in range(duration)
                ]
                self.do_animation_channel(
                    animation,
                    duration,
                    fps,
                    "translation",
                    translation,
                    anim_idx,
                    node_idx,
                    gltf,
                )

            if rotation is not None:
                rotation = [
                    list(rotation[c][f] for c in range(RotationChannels))
                    for f in range(duration)
                ]
                self.do_animation_channel(
                    animation,
                    duration,
                    fps,
                    "rotation",
                    rotation,
                    anim_idx,
                    node_idx,
                    gltf,
                )

            if scale is not None:
                scale = [
                    list(scale[c][f] for c in range(ScaleChannels))
                    for f in range(duration)
                ]

                self.do_animation_channel(
                    animation, duration, fps, "scale", scale, anim_idx, node_idx, gltf
                )

        # Create keyframes for pose
        for node_idx in range(len(gltf.data.nodes)):
            if node_idx in animation.used_nodes:
                continue

            vnode: VNode = gltf.vnodes[node_idx]  # type: ignore
            if vnode.type != VNode.Bone:
                continue

            node: "Node" = gltf.data.nodes[node_idx]

            # Translation
            translation = [node.translation or [0, 0, 0]]
            self.do_animation_channel(
                animation,
                1,
                fps,
                "translation",
                translation,
                anim_idx,
                node_idx,
                gltf,
            )

            # Rotation
            rotation = [node.rotation or [0, 0, 0, 1]]
            self.do_animation_channel(
                animation,
                1,
                fps,
                "rotation",
                rotation,
                anim_idx,
                node_idx,
                gltf,
            )

            # Scale
            scale = [node.scale or [1, 1, 1]]
            self.do_animation_channel(
                animation, 1, fps, "scale", scale, anim_idx, node_idx, gltf
            )
