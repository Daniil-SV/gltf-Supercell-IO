from io_scene_gltf2.blender.imp.vnode import VNode, reparent
from ...com.utilities.patcher import Patch
from ..components.component import is_valid_scgltf
from mathutils import Vector, Quaternion

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


skinned_mesh = Patch(
    "skinned mesh",
    module_path="io_scene_gltf2.blender.imp.vnode",
    target_method="move_skinned_meshes",
    function=move_skinned_meshes,
)
