from mathutils import Matrix
from .component import glTF2BaseExporterComponent, requires_extension
from ...com import glTF_material_extension_name, glTF_extension_name
from io_scene_gltf2.blender.exp.tree import VExportNode
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from io_scene_gltf2.io.com.gltf2_io import Gltf


class CommonExporter(glTF2BaseExporterComponent):
    def gather_extension(self, gltf: "Gltf", export_settings: dict):
        extension = {}
        if not self.properties.legacy_materials:
            materials = export_settings[glTF_material_extension_name]
            if len(materials):
                extension["materials"] = materials
                gltf.materials = []

        if extension:
            gltf.extensions[glTF_extension_name] = Extension(
                glTF_extension_name, extension, True
            )

    def gather_nodes_extension(self, gltf: "Gltf"):
        nodes = gltf.nodes or []
        parent_of = {}
        for i, node in enumerate(nodes):
            for child_idx in node.children or []:
                parent_of[child_idx] = i

        for i, node in enumerate(nodes):
            if node.extensions is None:
                node.extensions = {}

            extension = node.extensions.get(glTF_extension_name)
            if extension is None:
                extension = {}
                node.extensions[glTF_extension_name] = extension

            extension["parent"] = parent_of.get(i)

        for node in nodes:
            node.children = None

    @requires_extension
    def gather_gltf_extensions_hook(self, gltf, export_settings):
        self.gather_extension(gltf, export_settings)
        # self.gather_nodes_extension(gltf)
        gltf.asset.generator += " | Supercell-IO Exporter by DaniilSV"

    @requires_extension
    def pre_export_hook(self, export_settings: dict):
        if not self.properties.legacy_materials:
            export_settings[glTF_material_extension_name] = []

    @requires_extension
    def gather_joint_hook(self, node, blender_bone, export_settings):
        # A subset of Supercell joints carry a non-unit pose scale that the
        # importer moves out of the Blender pose into the
        # ``scScaleOverride`` custom property (see
        # ``importer/patches/vnodes.py``). For those bones we restore the
        # joint's exported TRS verbatim from the
        # ``scTranslationOverride``/``scRotationOverride``/``scScaleOverride``
        # custom properties rather than relying on the matrix decomposition
        # produced by ``gather_joint_vnode``.
        if blender_bone is None:
            return

        if "scScaleOverride" not in blender_bone:
            return

        sx, sy, sz = blender_bone["scScaleOverride"]
        tx = ty = tz = 0.0
        if "scTranslationOverride" in blender_bone:
            tx, ty, tz = blender_bone["scTranslationOverride"]
        rx = ry = rz = 0.0
        rw = 1.0
        if "scRotationOverride" in blender_bone:
            rx, ry, rz, rw = blender_bone["scRotationOverride"]

        # ``sc*Override`` stores values in Blender's coordinate system (Z-up)
        # and quaternion order (qx, qy, qz, qw). Convert back to glTF (Y-up
        # by default) using the same swizzle the default exporter uses
        # internally (see io_scene_gltf2/blender/exp/joints.py).
        if export_settings.get("gltf_yup", True):
            node.translation = (
                [tx, tz, -ty] if not (tx == 0.0 and ty == 0.0 and tz == 0.0) else None
            )
            node.rotation = (
                [rx, rz, -ry, rw]
                if not (rw == 1.0 and rx == 0.0 and ry == 0.0 and rz == 0.0)
                else None
            )
            node.scale = [sx, sz, sy]
        else:
            node.translation = (
                [tx, ty, tz] if not (tx == 0.0 and ty == 0.0 and tz == 0.0) else None
            )
            node.rotation = (
                [rx, ry, rz, rw]
                if not (rw == 1.0 and rx == 0.0 and ry == 0.0 and rz == 0.0)
                else None
            )
            node.scale = [sx, sy, sz]

    @requires_extension
    def vtree_before_filter_hook(self, vtree, export_settings):
        # Supercell files bake each scale-bearing joint's pose scale into the
        # ``scScaleOverride`` custom property on import (see
        # ``importer/patches/vnodes.py``). The Blender pose has the scale
        # stripped (so the armature modifier does not deform the mesh at
        # rest), so a naive re-export would write a unit node scale.
        #
        # Restoring the joint's scale is a right-multiply of the bone's
        # vtree ``matrix_world`` by a diagonal scale. Doing only this is
        # wrong, however: a scale-parent's S leaks into its descendants
        # when the export pipeline computes the child's local TRS via
        # ``parent.matrix_world.inverted() @ child.matrix_world`` -- the
        # parent's S^-1 multiplies the child's decomposition, which would
        # divide the child's exported scale by the parent's scale and
        # break round-trip.
        #
        # The leak is cancelled by ALSO right-multiplying each descendant
        # by the *cumulative* ancestor S. With ``S_ancestor`` already on
        # the right of the parent's ``matrix_world`` (because the parent's
        # own hook pass ran first), the rightmost S_ancestor commutes
        # through the parent's S and R (uniform for every joint we
        # encounter) and cancels the parent's leakage exactly. The result
        # is that
        #     * parent's exported TRS scale = parent's scScaleOverride
        #       (own S unaffected),
        #     * child's exported translation = file's translation (the
        #       bake we applied at import is divided back out), and
        #     * child's exported TRS scale = child's scScaleOverride (own
        #       S, not parent's leak).
        #
        # Cumulative chain ``1.84`` -> ``0.543478`` (1/1.84) -> ``1.84``
        # cancels pairwise so non-scale descendants stay unaffected.
        identity = (1.0, 1.0, 1.0)

        def _sanitize(value):
            if value is None:
                return identity
            x, y, z = value
            return (
                x if abs(x) > 1e-6 else 1.0,
                y if abs(y) > 1e-6 else 1.0,
                z if abs(z) > 1e-6 else 1.0,
            )

        def _own_scale(node):
            if node.blender_type != VExportNode.BONE or node.blender_bone is None:
                return identity
            return _sanitize(node.blender_bone.get("scScaleOverride"))

        # Top-down walk via vtree.roots and node.children; track the
        # cumulative per-axis ancestor scale so children's matrix_world can
        # be right-multiplied by
        # ``S(own) @ S(ancestor_accumulated)``. Parent always processed
        # before its children, so each bone sees its ancestors' final
        # combined scale.
        from collections import deque

        ancestor_cumulative = {}  # parent_uuid -> (sx, sy, sz)
        queue = deque(vtree.roots)

        while queue:
            key = queue.popleft()
            vnode: VExportNode = vtree.nodes[key]  # type: ignore

            parent_uuid = vnode.parent_uuid  # type: ignore
            parent_acc = ancestor_cumulative.get(parent_uuid, identity)

            ox, oy, oz = _own_scale(vnode)
            ax, ay, az = parent_acc

            # Cumulative scale that should be applied (rightmost) to THIS
            # bone's matrix_world = own scale * ancestor cumulative.
            cx, cy, cz = (ox * ax, oy * ay, oz * az)
            ancestor_cumulative[key] = (cx, cy, cz)

            if (
                vnode.blender_type == VExportNode.BONE
                and vnode.matrix_world is not None
                and (cx, cy, cz) != identity
            ):
                scale_matrix = Matrix.Diagonal((cx, cy, cz, 1.0))
                vnode.matrix_world = vnode.matrix_world @ scale_matrix  # type: ignore

            for child_uuid in vnode.children:
                queue.append(child_uuid)
