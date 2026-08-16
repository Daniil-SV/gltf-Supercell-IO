from ...com.utilities.patcher import Patch
from ..components.component import is_valid_scgltf
from mathutils import Vector, Quaternion, Matrix


def move_skinned_meshes(gltf):
    """
    In glTF, where in the node hierarchy a skinned mesh is instantiated has
    no effect on its world space position: only the world transforms of the
    joints in its skin affect it.

    To do this in Blender:
     * Move a skinned mesh to become a child of the armature that skins it.
       Have to ensure the mesh and arma have the same world transform.
     * When we do mesh creation, we will also need to put all the verts in
       the bind pose in arma space.
    """
    from io_scene_gltf2.blender.imp.vnode import VNode, reparent

    ids = list(gltf.vnodes.keys())
    for id in ids:
        vnode = gltf.vnodes[id]

        if vnode.mesh_node_idx is None:
            continue

        skin = gltf.data.nodes[vnode.mesh_node_idx].skin
        if skin is None:
            continue

        pyskin = gltf.data.skins[skin]
        arma = gltf.vnodes[pyskin.joints[0]].bone_arma

        # First try moving the whole node if we can do it without
        # messing anything up.
        is_animated = (
            gltf.data.animations
            and isinstance(id, int)
            and gltf.data.nodes[id].animations
        )
        ok_to_move = (
            not is_animated
            and vnode.type == VNode.Object
            and not vnode.is_arma
            and not vnode.children
            and vnode.camera_node_idx is None
            and vnode.light_node_idx is None
        )
        if ok_to_move:
            if is_valid_scgltf(gltf):
                continue

            # !!! BULLSHIT CODE ALERT !!!
            reparent(gltf, id, new_parent=arma)
            vnode.base_trs = (
                Vector((0, 0, 0)),
                Quaternion((1, 0, 0, 0)),
                Vector((1, 1, 1)),
            )
            continue

        # Otherwise, create a new child of the arma and move
        # the mesh instance there, leaving the node behind.
        new_id = str(id) + ".skinned"
        gltf.vnodes[new_id] = VNode()
        gltf.vnodes[new_id].parent = arma
        gltf.vnodes[arma].children.append(new_id)
        gltf.vnodes[new_id].mesh_node_idx = vnode.mesh_node_idx
        gltf.vnodes[new_id].scenes = vnode.scenes
        vnode.mesh_node_idx = None


# Pose scale baking
#
# Some Supercell glTF files store a non-uniform or non-unit scale on a node
# that the renderer simply multiplies into the bone's world matrix (a
# "pose scale" -> the engine bakes the inverse of the scaled bind matrix into
# the inverse bind matrices)
#
# Blender edit bones cannot store a per-bone rest scale, so leaving the scale
# in the bone's pose causes the armature modifier to scale vertices at the
# rest pose (because Blender uses `bone.matrix_local` for skinning and
# `matrix_local` always has unit scale). That produces the visible artifact
# the importer is trying to avoid
#
# Strategy:
#   * The node's own scale is moved out of the pose (`base_trs` scale set to
#     ``(1, 1, 1)``) and preserved as ``sc_scale_override`` per vnode.
#     It is later written onto the pose bone as the ``scScaleOverride``
#     custom property, which is consumed by the exporter to reconstruct the
#     identical inverse bind matrices and node scales
#   * The cumulative scale of scale-bearing ancestors is baked into every
#     child bone's rest translation (``editbone_trans`` and ``bind_trans``)
#     so the Blender edit skeleton visually matches the SC skeleton. To keep
#     the pose at rest identical to the actual bind pose, the child's ``base_trs`` translation
#     is set to the *new* (already scaled) edit translation. This makes the
#     default pose bone location at rest zero
#   * The cumulative ancestor scale that was applied to a bone's translation
#     is recorded on the vnode as ``sc_translate_factor``. Animation channels
#     for translation then multiply each keyframe value by this factor (so
#     the file's translation, which is stored in the parent bone's scaled
#     local frame, lands at the correct world position) and channels for
#     scale divide by ``sc_scale_override`` (so the absolute node scale
#     that the SC engine renders with does not re-introduce the rest pose
#     artifact)
#   * The original (un-baked) node TRS is recorded on the vnode as
#     ``sc_tr_override``, which the importer later writes onto the pose
#     bone as ``scTranslationOverride``/``scRotationOverride``/``scScaleOverride``.
#     The exporter uses these to set the joint's exported TRS directly,
#     avoiding the ambiguities of matrix decomposition for non-uniform
#     (e.g. Z-reflective) scales
def bake_pose_scale_into_vnodes(gltf):
    from io_scene_gltf2.blender.imp.vnode import VNode

    vnodes = gltf.vnodes
    identity = Matrix.Identity(4)

    def has_scale(scale):
        return (
            abs(scale.x - 1.0) > 1e-6
            or abs(scale.y - 1.0) > 1e-6
            or abs(scale.z - 1.0) > 1e-6
        )

    def scale_matrix(scale):
        return Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))

    # Snapshot of the original data for every bone vnode. We only read the
    # snapshot while walking the tree so modifications made during the walk
    # never feed back into the snapshot lookups
    original_base_trs = {
        vnode_id: vnode.base_trs
        for vnode_id, vnode in vnodes.items()
        if vnode.type == VNode.Bone
    }
    original_edit_trans = {
        vnode_id: Vector(vnode.editbone_trans)
        for vnode_id, vnode in vnodes.items()
        if vnode.type == VNode.Bone
    }
    original_bind_trans = {
        vnode_id: Vector(vnode.bind_trans)
        for vnode_id, vnode in vnodes.items()
        if vnode.type == VNode.Bone
    }

    def visit(vnode_id, accumulated_scale):
        vnode = vnodes[vnode_id]
        own_scale = identity

        # Move this bone's own scale out of the pose and remember it
        if vnode.type == VNode.Bone:
            translation, rotation, scale = original_base_trs[vnode_id]

            if has_scale(scale):
                own_scale = scale_matrix(scale)

                # Guard zero entries so existing logic that divides by the
                # override never actually divides by zero. Real files do
                # not store zero scale on a joint
                def _safe_scale(v):
                    return v if v != 0.0 else 1.0

                vnode.sc_scale_override = (
                    _safe_scale(scale.x),
                    _safe_scale(scale.y),
                    _safe_scale(scale.z),
                )

                # Save the full original TRS so the exporter can write the
                # joint's node TRS verbatim (skipping matrix decomposition,
                # which is ambiguous for negative/non-uniform scales).
                # The values are kept in Blender's coordinate system /
                # quaternion order; the export ``gather_joint_hook``
                # performs the same Y-up swizzle io_scene_gltf2 uses
                # internally
                vnode.sc_tr_override = (
                    translation.x,
                    translation.y,
                    translation.z,
                    rotation.x,
                    rotation.y,
                    rotation.z,
                    rotation.w,
                    _safe_scale(scale.x),
                    _safe_scale(scale.y),
                    _safe_scale(scale.z),
                )

                # The bone's translation is the *baked* one already
                # written to ``editbone_trans`` by the parent pass, so use
                # it as the new base TRS translation. This keeps
                # ``pose_bone.location = edit_rot^-1 @ (t - et)`` evaluating
                # to zero at the rest pose (``t == et``)
                vnode.base_trs = (
                    Vector(vnode.editbone_trans),
                    rotation,
                    Vector((1.0, 1.0, 1.0)),
                )

        # The cumulative scale that originally affected the local
        # coordinate frame of this vnode's children
        child_accumulated = accumulated_scale @ own_scale

        # ``accumulated_scale`` is the per-axis factor that was used to
        # bake this vnode's own edit translation. Animation channels for
        # translation need to multiply file translations by exactly this
        # factor to land in the baked coordinate frame. The cumulative
        # matrix is always diagonal (products of diagonal scale matrices),
        # so a simple per-axis tuple is sufficient
        if accumulated_scale != identity:
            vnode.sc_translate_factor = (
                accumulated_scale[0][0],
                accumulated_scale[1][1],
                accumulated_scale[2][2],
            )
        else:
            vnode.sc_translate_factor = (1.0, 1.0, 1.0)

        # Bake the accumulated ancestor scale into the rest skeleton of
        # every bone child so the Blender edit bone sits exactly where the
        # SC engine places the joint at bind time. The recursion itself
        # is run for *all* children (not just bones) so scale-bearing
        # ancestors deep inside a non-bone subtree still propagate.
        for child_id in vnode.children:
            is_bone_child = vnodes[child_id].type == VNode.Bone

            if is_bone_child:
                child = vnodes[child_id]

                old_edit = original_edit_trans[child_id]
                new_edit = Vector(child_accumulated @ old_edit)

                old_bind = original_bind_trans[child_id]
                new_bind = Vector(child_accumulated @ old_bind)

                child.editbone_trans = new_edit
                child.bind_trans = new_bind

                # Keep the original rotation and the child's own scale
                # untouched (the child's own scale is processed when
                # ``visit`` recurses into it). The translation does not
                # need to be set here: when the child has no own scale it
                # already equals ``editbone_trans``; when the child has an
                # own scale its own ``visit`` resets ``base_trs`` using
                # the freshly baked ``editbone_trans``

            visit(child_id, child_accumulated)

    visit("root", identity)


def compute_vnodes(gltf):
    from io_scene_gltf2.blender.imp.vnode import (
        init_vnodes,
        mark_bones_and_armas,
        fixup_multitype_nodes,
        correct_cameras_and_lights,
        pick_bind_pose,
        prettify_bones,
        calc_bone_matrices,
    )

    init_vnodes(gltf)
    mark_bones_and_armas(gltf)
    move_skinned_meshes(gltf)
    fixup_multitype_nodes(gltf)
    correct_cameras_and_lights(gltf)
    pick_bind_pose(gltf)
    bake_pose_scale_into_vnodes(gltf)
    prettify_bones(gltf)
    calc_bone_matrices(gltf)


vnodes_compute_patch = Patch(
    "vnode compute",
    module_path="io_scene_gltf2.blender.imp.vnode",
    target_method="compute_vnodes",
    function=compute_vnodes,
)
