import bpy
from pathlib import Path
from typing import TYPE_CHECKING, Any
from mathutils import Matrix
from .component import glTF2BaseImporterComponent, requires_extension

from io_scene_gltf2.blender.imp.vnode import VNode
from io_scene_gltf2.blender.imp.animation_utils import make_fcurve

if TYPE_CHECKING:
    from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter


class AnimationImporter(glTF2BaseImporterComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.armature: bpy.types.Object | None = None

    def get_selected_armature(self):
        ctx = bpy.context
        layer = ctx.view_layer
        if layer is None:
            return

        for selected in layer.objects.selected:
            if isinstance(selected, bpy.types.Object) and selected.type == "ARMATURE":
                return selected

        return None

    def get_gltf_armature(
        self, root_idx: Any, gltf: "glTFImporter"
    ) -> bpy.types.Object | None:
        vnodes: dict[Any, VNode] = gltf.vnodes  # type: ignore
        vnode = vnodes[root_idx]
        if hasattr(vnode, "is_arma") and vnode.is_arma:
            return vnode.blender_object  # type: ignore

        for children in vnode.children:
            armature = self.get_gltf_armature(children, gltf)
            if armature is not None:
                return armature

    def get_action_range(self, source: bpy.types.Object) -> tuple[int, int]:
        anim = source.animation_data
        if anim and anim.action:
            start, end = anim.action.frame_range
            return int(start), int(end)
        return (0, 0)

    def compute_rest_offset(self, target: bpy.types.Object):
        """rest_offset[name] transforms a target bone's matrix_basis into its
        armature-local pose matrix:
            pose_matrix = parent_pose_matrix @ rest_offset @ matrix_basis
        For root bones, rest_offset = bone.matrix_local (parent_pose_matrix = I).
        """
        if not isinstance(target.data, bpy.types.Armature):
            return {}

        rest: dict[str, Matrix] = {}
        for bone in target.data.bones:
            if bone.parent:
                rest[bone.name] = (
                    bone.parent.matrix_local.inverted_safe() @ bone.matrix_local
                )
            else:
                rest[bone.name] = bone.matrix_local
        return rest

    def sort_bones(self, target: bpy.types.Object):
        """Return target bone names ordered so parents come before children."""
        order: list[str] = []
        visited = set()
        if not isinstance(target.data, bpy.types.Armature):
            return order

        def visit(bone):
            if bone.name in visited:
                return
            if bone.parent:
                visit(bone.parent)
            visited.add(bone.name)
            order.append(bone.name)

        for b in target.data.bones:
            visit(b)

        return order

    def orphan_object(self, root: bpy.types.Object):
        objects = []

        def collect(obj):
            try:
                for child in obj.children:
                    collect(child)

                objects.append(obj)
            except ReferenceError:
                pass

        collect(root)
        for obj in objects:
            data = obj.data
            action = obj.animation_data.action if obj.animation_data else None

            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0:
                match type(data):
                    case bpy.types.Mesh:
                        bpy.data.meshes.remove(data)
                    case bpy.types.Armature:
                        bpy.data.armatures.remove(data)
                    case bpy.types.Curve:
                        bpy.data.curves.remove(data)
                    case bpy.types.Camera:
                        bpy.data.cameras.remove(data)
                    case bpy.types.Light:
                        bpy.data.lights.remove(data)

            if action and action.users == 0:
                bpy.data.actions.remove(action)

    def retarget_animation(
        self, source: bpy.types.Object, target: bpy.types.Object, fallback_name: str
    ):
        if not isinstance(source.data, bpy.types.Armature) or not isinstance(
            target.data, bpy.types.Armature
        ):
            return False

        scene = bpy.context.scene
        if scene is None:
            return False

        source_animation = source.animation_data
        target_animation = target.animation_data
        if target_animation is None:
            target_animation = target.animation_data_create()

        start, end = self.get_action_range(source)
        rest_offset = self.compute_rest_offset(target)
        bones = self.sort_bones(target)

        # World-armature conversion (armature-local space) from source to target
        sw_to_tw = target.matrix_world.inverted_safe() @ source.matrix_world

        # Validate that every target bone (and its parent) exists in source by name
        src_pose = source.pose
        tgt_pose = target.pose
        if src_pose is None or tgt_pose is None:
            return False

        # Paired = bones that exist by the same name in source.
        # Intermediate bones (e.g. ":SSC" helpers in target but not in source)
        # are left at rest (matrix_basis = identity), exactly as the
        # constraint+bake approach leaves unconstrained bones at rest.
        paired_set = set(n for n in bones if n in src_pose.bones)
        pairs = [n for n in bones if n in paired_set]

        # Force quaternion mode on the bones we are going to keyframe (matches glb)
        for bone in pairs:
            tgt_pose.bones[bone].rotation_mode = "QUATERNION"

        if source_animation is None or source_animation.action is None:
            action = bpy.data.actions.new(fallback_name)
        else:
            action = source_animation.action

        target_animation.action = action
        if target_animation.action_slot is None:
            slot = action.slots.new(target.id_type, target.name)
            target_animation.action_slot = slot
        else:
            slot = target_animation.action_slot

        if len(action.layers) == 0:
            action.layers.new("layer0")
            action.layers[0].strips.new(type="KEYFRAME")
        action.layers[0].strips[0].channelbags.new(slot)  # type: ignore

        # Cache parents once
        parent_of = {
            n: (
                target.data.bones[n].parent.name  # type: ignore
                if target.data.bones[n].parent
                else None
            )
            for n in bones
        }

        # Build the explicit list of frames we will iterate, and size everything
        # to THAT list rather than to a separately-computed num_frames (which
        # can drift in edge cases around int() / float boundary rounding).
        # Using a single source of truth guarantees buffer size always matches
        # iteration count.
        iter_frames = list(range(start, end + 1))
        num_frames = len(iter_frames)

        # Per-bone, per-component parallel value lists (length num_frames each).
        # Storing components separately makes them directly sliceable into the
        # flat coords buffer used by make_fcurve
        loc_vals: dict[str, list[list[float]]] = {
            n: [[0.0] * num_frames for _ in range(3)] for n in pairs
        }
        rot_vals: dict[str, list[list[float]]] = {
            n: [[0.0] * num_frames for _ in range(4)] for n in pairs
        }
        scl_vals: dict[str, list[list[float]]] = {
            n: [[0.0] * num_frames for _ in range(3)] for n in pairs
        }

        # Frame indices shared across every fcurve.
        frame_indices = iter_frames

        identity = Matrix.Identity(4)
        for fi, f in enumerate(iter_frames):
            scene.frame_set(f)

            # Source (armature-local) pose matrices for this frame, for paired bones.
            src_mats = {n: src_pose.bones[n].matrix for n in pairs}

            # Walk the entire target chain top-down. For each bone we compute its
            # pose matrix (armature-local) recursively from its parent's pose:
            #
            #   pose = parent_pose @ rest_offset @ matrix_basis
            #
            # Paired bones: matrix_basis is solved so that pose = sw_to_tw @ src.
            # Non-paired (intermediate) bones: matrix_basis = identity, so their
            # pose is simply parent_pose @ rest_offset (rest-relative placement).
            pose_cache: dict[str, Matrix] = {}
            for bone in bones:
                pname = parent_of[bone]
                parent_pose = pose_cache[pname] if pname is not None else identity
                if bone in paired_set:
                    desired = sw_to_tw @ src_mats[bone]
                    basis = (
                        rest_offset[bone].inverted_safe()
                        @ parent_pose.inverted_safe()
                        @ desired
                    )
                    pose = desired
                else:
                    basis = identity
                    pose = parent_pose @ rest_offset[bone]
                pose_cache[bone] = pose

                # Decompose the matrix_basis of paired bones directly into their channel value lists
                if bone in paired_set:
                    loc, quat, scale = basis.decompose()

                    sx, sy, sz = 1, 1, 1
                    if "scScaleOverride" in tgt_pose.bones[bone]:
                        sx, sy, sz = tgt_pose.bones[bone]["scScaleOverride"]

                    loc_vals[bone][0][fi] = loc.x
                    loc_vals[bone][1][fi] = loc.y
                    loc_vals[bone][2][fi] = loc.z
                    # Quaternion fcurve indices are in Blender's (w, x, y, z)
                    # component order, matching mathutils.Quaternion iteration
                    # and the io_scene_gltf2 importer convention.
                    rot_vals[bone][0][fi] = quat.w
                    rot_vals[bone][1][fi] = quat.x
                    rot_vals[bone][2][fi] = quat.y
                    rot_vals[bone][3][fi] = quat.z
                    scl_vals[bone][0][fi] = scale.x * (1 / sx)
                    scl_vals[bone][1][fi] = scale.y * (1 / sy)
                    scl_vals[bone][2][fi] = scale.z * (1 / sz)

        # Ensure quaternion rotations take the shortest arc by flipping adjacent
        # antipodal quaternions -- the same nla.bake / io_scene_gltf2 pass that
        # smooths rotation interpolation. Without this, sign flips from per-frame
        # matrix decomposition cause the action to spin between keyframes.
        for bone in pairs:
            rx, ry, rz, rw = rot_vals[bone]
            px = rx[0]
            py = ry[0]
            pz = rz[0]
            pw = rw[0]
            for fi in range(1, num_frames):
                cx = rx[fi]
                cy = ry[fi]
                cz = rz[fi]
                cw = rw[fi]
                if cx * px + cy * py + cz * pz + cw * pw < 0:
                    cx = -cx
                    cy = -cy
                    cz = -cz
                    cw = -cw
                    rx[fi] = cx
                    ry[fi] = cy
                    rz[fi] = cz
                    rw[fi] = cw
                px, py, pz, pw = cx, cy, cz, cw

        coords = [0.0] * (2 * num_frames)
        coords[::2] = frame_indices
        for bone in pairs:
            esc = bpy.utils.escape_identifier(bone)
            rna_base = 'pose.bones["%s"]' % esc
            for i in range(3):
                coords[1::2] = loc_vals[bone][i]
                make_fcurve(
                    action,
                    slot,
                    coords,
                    data_path="%s.location" % rna_base,
                    index=i,
                    group_name=bone,
                )
            for i in range(4):
                coords[1::2] = rot_vals[bone][i]
                make_fcurve(
                    action,
                    slot,
                    coords,
                    data_path="%s.rotation_quaternion" % rna_base,
                    index=i,
                    group_name=bone,
                )
            for i in range(3):
                coords[1::2] = scl_vals[bone][i]
                make_fcurve(
                    action,
                    slot,
                    coords,
                    data_path="%s.scale" % rna_base,
                    index=i,
                    group_name=bone,
                )

        # Apply the first frame to the target skeleton so the user sees the
        # rest frame on the retargeted pose without needing to scrub.
        scene.frame_set(start)

        # Cleanup
        if source_animation is not None and source_animation.action_slot is not None:
            action.slots.remove(source_animation.action_slot)

        scene.frame_start = start
        scene.frame_end = end
        return True

    @requires_extension
    def gather_import_gltf_before_hook(self, gltf):
        self.armature = self.get_selected_armature()

    @requires_extension
    def gather_import_scene_after_animation_hook(self, gltf_scene, blender_scene, gltf):
        if not self.properties.apply_animation:
            return

        if gltf_scene is None:
            return

        if self.armature is None:
            return

        retarget_armatures: set[str] = set()
        gltf_armature = self.get_gltf_armature("root", gltf)
        if gltf_armature is None:
            return

        if gltf_armature.name_full in retarget_armatures:
            return

        name = Path(gltf.filename).stem
        retarget_armatures.add(gltf_armature.name_full)

        success = self.retarget_animation(gltf_armature, self.armature, name)
        vnodes: dict[Any, VNode] = gltf.vnodes  # type: ignore

        if success:
            gltf.import_settings["import_select_created_objects"] = False

            for idx in gltf_scene.nodes or []:
                vnode = vnodes.get(idx)
                if vnode is None:
                    continue

                if hasattr(vnode, "blender_object"):
                    self.orphan_object(vnode.blender_object)  # type: ignore
                elif vnode.parent is not None:
                    self.orphan_object(vnodes[vnode.parent].blender_object)  # type: ignore
