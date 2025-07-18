import bpy
from bpy.types import (
    Operator,
)

from . import json_helpers


class SR_OT_RigList_Add(Operator):
    """Add a new effect to the list."""

    bl_idname = "shading_rig.list_add"
    bl_label = "Add Effect"
    bl_description = "Create a new Empty as a new effect"

    @classmethod
    def poll(cls, context):
        if json_helpers.get_scene_properties_object() is None:
            # This can happen at startup, so don't set a poll message
            return False

        if not context.scene.shading_rig_default_material:
            cls.poll_message_set("Please set up a default material for the rig first.")
            return False

        return True

    def execute(self, context):
        scene = context.scene
        cursor_location = scene.cursor.location
        rig_list = scene.shading_rig_list

        new_item = rig_list.add()

        if scene.shading_rig_default_material:
            new_item.material = scene.shading_rig_default_material

        if scene.shading_rig_default_light:
            new_item.light_object = scene.shading_rig_default_light

        bpy.ops.object.empty_add(type="SPHERE", location=cursor_location)
        new_empty = context.active_object
        new_empty.empty_display_size = 0.15
        new_empty.show_name = True
        new_empty.show_in_front = True

        new_item.empty_object = new_empty

        new_item.name = (
            f"SR_Effect_{scene.shading_rig_chararacter_name}_{len(rig_list):03d}"
        )

        new_item.last_empty_name = new_item.name

        json_helpers.set_shading_rig_list_index(len(rig_list) - 1)

        objects_with_material = []
        for obj in bpy.data.objects:
            if any(s.material == new_item.material for s in obj.material_slots):
                objects_with_material.append(obj)

        print(
            f"Objects with material '{new_item.material.name}': {len(objects_with_material)} found."
        )

        rig_index = len(rig_list) - 1

        for obj in objects_with_material:
            packed_prop_name = f"packed:{new_item.name}"
            obj[packed_prop_name] = [0, 0, 0]

            # Create drivers for each channel (0=red, 1=green, 2=blue)
            for channel in range(3):
                fcurve = obj.driver_add(f'["{packed_prop_name}"]', channel)
                driver = fcurve.driver
                driver.type = "SCRIPTED"

                # Create input variables as Context Properties
                var_names = [
                    "elongation",
                    "sharpness",
                    "bulge",
                    "bend",
                    "hardness",
                    "mode",
                    "clamp",
                    "rotation"
                ]
                var_paths = [
                    f"shading_rig_list[{rig_index}].elongation",
                    f"shading_rig_list[{rig_index}].sharpness",
                    f"shading_rig_list[{rig_index}].bulge",
                    f"shading_rig_list[{rig_index}].bend",
                    f"shading_rig_list[{rig_index}].hardness",
                    f"shading_rig_list[{rig_index}].mode",
                    f"shading_rig_list[{rig_index}].clamp",
                    f"shading_rig_list[{rig_index}].rotation",
                ]

                # Create driver variables
                for var_name, var_path in zip(var_names, var_paths):
                    var = driver.variables.new()
                    var.name = var_name
                    var.type = "CONTEXT_PROP"
                    var.targets[0].context_property = "ACTIVE_SCENE"
                    var.targets[0].data_path = var_path

                # Set the expression to use the input variables
                driver.expression = (
                    f"bpy.packing_algorithm("
                    f"elongation, sharpness, bulge, bend, hardness, mode, clamp, rotation)[{channel}]"
                )

        json_helpers.sync_scene_to_json(context.scene)

        return {"FINISHED"}


class SR_OT_Correlation_Add(Operator):
    """Add a new correlation to the active rig."""

    bl_idname = "shading_rig.correlation_add"
    bl_label = "Add Correlation"
    bl_description = "Add a new correlation to the active rig"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not (
            json_helpers.get_shading_rig_list_index() >= 0
            and len(scene.shading_rig_list) > 0
        ):
            cls.poll_message_set("No effects in the list.")
            return False

        if not scene.shading_rig_list[
            json_helpers.get_shading_rig_list_index()
        ].light_object:
            cls.poll_message_set("Active effect has no Light Object assigned.")
            return False

        if not scene.shading_rig_list[
            json_helpers.get_shading_rig_list_index()
        ].empty_object:
            cls.poll_message_set("Active effect has no Empty Object assigned.")
            return False

        if not scene.shading_rig_chararacter_name:
            cls.poll_message_set("Please set a character name.")
            return False

        if not scene.shading_rig_list[
            json_helpers.get_shading_rig_list_index()
        ].added_to_material:
            cls.poll_message_set("Add the effect to a material first.")
            return False

        return True

    def execute(self, context):
        try:
            scene = context.scene
            active_rig_item = scene.shading_rig_list[
                json_helpers.get_shading_rig_list_index()
            ]

            light_obj = active_rig_item.light_object
            empty_obj = active_rig_item.empty_object

            if not light_obj or not empty_obj:
                self.report(
                    {"ERROR"}, "Active effect has no Light or Empty Object assigned."
                )
                return {"CANCELLED"}

            new_corr = active_rig_item.correlations.add()
            new_corr.name = f"Correlation_{scene.shading_rig_chararacter_name}_{len(active_rig_item.correlations):03d}"

            new_corr.light_rotation = light_obj.rotation_euler
            new_corr.empty_position = empty_obj.location
            new_corr.empty_scale = empty_obj.scale
            new_corr.empty_rotation = empty_obj.rotation_euler

            active_rig_item.correlations_index = len(active_rig_item.correlations) - 1

            self.report({"INFO"}, f"Stored pose in '{new_corr.name}'.")

        except Exception as e:
            self.report({"ERROR"}, "Failed to add correlation. " + str(e))
            return {"CANCELLED"}

        json_helpers.sync_scene_to_json(context.scene)
        return {"FINISHED"}


class SR_OT_Correlation_Remove(Operator):
    """Remove the selected correlation from the active effect."""

    bl_idname = "shading_rig.correlation_remove"
    bl_label = "Remove Correlation"
    bl_description = "Remove the selected correlation from the active effect"

    @classmethod
    def poll(cls, context):
        scene = context.scene

        if not (
            json_helpers.get_shading_rig_list_index() >= 0
            and len(scene.shading_rig_list) > 0
        ):
            cls.poll_message_set("No effects in the list.")
            return False
        active_rig_item = scene.shading_rig_list[
            json_helpers.get_shading_rig_list_index()
        ]
        return len(active_rig_item.correlations) > 0

    def execute(self, context):
        scene = context.scene
        active_rig_item = scene.shading_rig_list[
            json_helpers.get_shading_rig_list_index()
        ]
        index = active_rig_item.correlations_index

        if index >= len(active_rig_item.correlations):
            return {"CANCELLED"}

        removed_name = active_rig_item.correlations[index].name
        active_rig_item.correlations.remove(index)

        if index > 0:
            active_rig_item.correlations_index = index - 1
        else:
            active_rig_item.correlations_index = 0

        self.report({"INFO"}, f"Removed correlation '{removed_name}' from effect.")
        json_helpers.sync_scene_to_json(context.scene)
        return {"FINISHED"}


class SR_OT_RigList_Remove(Operator):
    """Remove the selected rig from the list."""

    bl_idname = "shading_rig.list_remove"
    bl_label = "Remove Effect"
    bl_description = (
        "Remove the selected effect and its associated objects from the scene"
    )

    @classmethod
    def poll(cls, context):
        return len(context.scene.shading_rig_list) > 0

    def execute(self, context):
        scene = context.scene
        rig_list = scene.shading_rig_list
        index = json_helpers.get_shading_rig_list_index()

        if index >= len(rig_list):
            return {"CANCELLED"}

        item_to_remove = rig_list[index]

        # TODO: Remove material nodes

        objects_to_delete = []
        if item_to_remove.empty_object:
            objects_to_delete.append(item_to_remove.empty_object)

        rig_list.remove(index)

        if index > 0:
            json_helpers.set_shading_rig_list_index(index - 1)
        else:
            json_helpers.set_shading_rig_list_index(0)

        if objects_to_delete:
            bpy.ops.object.select_all(action="DESELECT")
            for obj in objects_to_delete:
                if obj.name in bpy.data.objects:
                    bpy.data.objects[obj.name].select_set(True)
            bpy.ops.object.delete()

        json_helpers.sync_scene_to_json(context.scene)

        return {"FINISHED"}
