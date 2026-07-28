from io_scene_gltf2.blender.exp.exporter import GlTF2Exporter
from ...com.utilities.patcher import Patch

# NOTE: target_method uses the name-mangled identifier "_GlTF2Exporter__traverse"
# (not "__traverse"), because setattr() does not apply Python name mangling.
# Inside the class, "self.__traverse(...)" is compiled to "self._GlTF2Exporter__traverse(...)",
# so we must override that exact attribute for the patch to take effect.

_orig_traverse = GlTF2Exporter._GlTF2Exporter__traverse  # type: ignore # plain function(self, node)


def traverse(self, node):
    lookup = self._GlTF2Exporter__childOfRootPropertyTypeLookup
    root_list = lookup.get(type(node))
    if root_list is None:
        # Not a ChildOfRootProperty -> delegate to the original implementation
        # (handles lists, dicts, plain property types, BinaryData, ImageData, Extensions, etc.)
        return _orig_traverse(self, node)

    # Register the node in its root-level list BEFORE traversing its members,
    # so any back-reference (cycle through skin.joints -> bone -> ... -> mesh -> skin)
    # resolves to the already-assigned index instead of recursing forever.
    for i, existing in enumerate(root_list):
        if existing is node:
            return i
    idx = len(root_list)
    root_list.append(node)
    self._GlTF2Exporter__traverse_property(node)
    return idx


traverse_gather = Patch(
    "exporter traverse cycle guard",
    module_path="io_scene_gltf2.blender.exp.exporter",
    target_class="GlTF2Exporter",
    target_method="_GlTF2Exporter__traverse",
    function=traverse,
)
