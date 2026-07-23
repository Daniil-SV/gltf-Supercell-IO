import bpy
from bpy.types import (
    PropertyGroup,
    Operator,
    UIList,
)
from bpy.props import (
    StringProperty,
)


class STRING_ARRAY_STATE(bpy.types.PropertyGroup):
    active_index: bpy.props.IntProperty(default=0)


def get_state():
    return bpy.context.window_manager.scgltf_string_array_state  # type: ignore


class StringItem(PropertyGroup):
    value: StringProperty(name="Value", default="")


class DirectoryStringItem(PropertyGroup):
    value: StringProperty(name="Value", subtype="DIR_PATH", default="")


class StringArray:

    @staticmethod
    def draw(layout, data_path, collection_prop, label="Items", default_value=""):

        data = bpy.context.path_resolve(data_path)
        state = get_state()

        layout.label(text=label)

        # LIST
        layout.template_list(
            "STRING_ARRAY_UL_items", "", data, collection_prop, state, "active_index"
        )

        row = layout.row(align=True)

        add = row.operator("string_array.add", text="Add", icon="ADD")
        add.data_path = data_path
        add.collection_prop = collection_prop
        add.default_value = default_value

        remove = row.operator("string_array.remove", text="Remove", icon="REMOVE")
        remove.data_path = data_path
        remove.collection_prop = collection_prop


class STRING_ARRAY_UL_items(UIList):
    def draw_item(
        self,
        context: bpy.types.Context,
        layout: bpy.types.UILayout,
        data,
        item,
        icon: int | None,
        active_data,
        active_property: str | None,
        index: int | None,
        flt_flag: int | None,
    ):
        state = get_state()

        if (
            active_property is not None
            and active_data == data
            and getattr(active_data, active_property, 0) != index
        ):
            state.active_index = index

        layout.prop(item, "value", text="")


class STRING_ARRAY_OT_add(Operator):
    bl_idname = "string_array.add"
    bl_label = "Add String"

    data_path: StringProperty()
    collection_prop: StringProperty()
    default_value: StringProperty(default="")

    def execute(self, context) -> set:
        try:
            data = context.path_resolve(self.data_path)
        except Exception:
            self.report({"ERROR"}, f"Invalid data path: {self.data_path}")
            return {"CANCELLED"}

        collection = getattr(data, self.collection_prop, None)

        if collection is None:
            self.report({"ERROR"}, f"Missing collection: {self.collection_prop}")
            return {"CANCELLED"}

        item = collection.add()
        item.value = self.default_value

        return {"FINISHED"}


class STRING_ARRAY_OT_remove(Operator):
    bl_idname = "string_array.remove"
    bl_label = "Remove"

    data_path: StringProperty()
    collection_prop: StringProperty()

    def execute(self, context) -> set:
        data = context.path_resolve(self.data_path)
        collection = getattr(data, self.collection_prop, None)

        if not collection:
            return {"CANCELLED"}

        state = get_state()
        index = state.active_index

        if 0 <= index < len(collection):
            collection.remove(index)
            state.active_index = max(0, index - 1)

        return {"FINISHED"}
