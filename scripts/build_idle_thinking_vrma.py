# -*- coding: utf-8 -*-
"""Build the looping idle and thinking VRMA clips for Haihe Girl.

Run with Blender, for example:

    blender --background --python scripts/build_idle_thinking_vrma.py -- \
      frontend/public/models/haihe-girl.vrm frontend/public/animations
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Euler, Quaternion, Vector


FPS = 30
RAD = math.pi / 180.0
HUMAN_BONES = [
    "hips",
    "spine",
    "chest",
    "upperChest",
    "neck",
    "head",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
    "leftIndexProximal",
    "leftIndexIntermediate",
    "leftIndexDistal",
    "leftMiddleProximal",
    "leftMiddleIntermediate",
    "leftMiddleDistal",
    "leftRingProximal",
    "leftRingIntermediate",
    "leftRingDistal",
    "leftLittleProximal",
    "leftLittleIntermediate",
    "leftLittleDistal",
    "leftThumbProximal",
    "leftThumbDistal",
    "rightIndexProximal",
    "rightIndexIntermediate",
    "rightIndexDistal",
    "rightMiddleProximal",
    "rightMiddleIntermediate",
    "rightMiddleDistal",
    "rightRingProximal",
    "rightRingIntermediate",
    "rightRingDistal",
    "rightLittleProximal",
    "rightLittleIntermediate",
    "rightLittleDistal",
    "rightThumbProximal",
    "rightThumbDistal",
]


def parse_args():
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("output_dir")
    parser.add_argument("--preview-dir")
    return parser.parse_args(script_args)


def qx(degrees):
    return Euler((degrees * RAD, 0, 0), "XYZ").to_quaternion()


def qy(degrees):
    return Euler((0, degrees * RAD, 0), "XYZ").to_quaternion()


def qz(degrees):
    return Euler((0, 0, degrees * RAD), "XYZ").to_quaternion()


def scale_quaternion(quaternion, scale):
    axis, angle = quaternion.to_axis_angle()
    return Quaternion(axis, angle * scale)


def smoothstep(start, end, value):
    if end <= start:
        return 0.0
    ratio = max(0.0, min(1.0, (value - start) / (end - start)))
    return ratio * ratio * (3.0 - 2.0 * ratio)


args = parse_args()
model_path = os.path.abspath(args.model)
output_dir = os.path.abspath(args.output_dir)
os.makedirs(output_dir, exist_ok=True)
preview_dir = os.path.abspath(args.preview_dir) if args.preview_dir else None
if preview_dir:
    os.makedirs(preview_dir, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.vrm(filepath=model_path)

armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
armature.location = (0, 0, 0)
armature.rotation_euler = (0, 0, 0)
armature.scale = (1, 1, 1)
armature.data.pose_position = "POSE"

scene = bpy.context.scene
scene.render.fps = FPS
vrm1 = armature.data.vrm_addon_extension.vrm1
human_bone_map = vrm1.humanoid.human_bones.human_bone_name_to_human_bone()
bone_names = {
    human_bone_name.value: human_bone.node.bone_name
    for human_bone_name, human_bone in human_bone_map.items()
    if human_bone_name.value in HUMAN_BONES
    and human_bone.node
    and human_bone.node.bone_name in armature.pose.bones
}
required = {
    "hips",
    "spine",
    "chest",
    "upperChest",
    "neck",
    "head",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
}
missing = sorted(required - bone_names.keys())
if missing:
    raise RuntimeError(f"Missing required humanoid bones: {', '.join(missing)}")

pose_bones = armature.pose.bones

if preview_dir:
    camera_data = bpy.data.cameras.new("AnimationPreviewCamera")
    camera = bpy.data.objects.new("AnimationPreviewCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, -1.9, 1.32)
    camera.rotation_euler = Euler((math.radians(90), 0, 0))
    scene.camera = camera

    key_data = bpy.data.lights.new("AnimationPreviewKey", "AREA")
    key_data.energy = 850
    key_data.shape = "DISK"
    key_data.size = 4.0
    key = bpy.data.objects.new("AnimationPreviewKey", key_data)
    scene.collection.objects.link(key)
    key.location = (1.8, -2.8, 3.2)
    key.rotation_euler = Euler((math.radians(35), 0, math.radians(28)))

    fill_data = bpy.data.lights.new("AnimationPreviewFill", "AREA")
    fill_data.energy = 420
    fill_data.size = 3.0
    fill = bpy.data.objects.new("AnimationPreviewFill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (-2.2, -1.6, 2.2)
    fill.rotation_euler = Euler((math.radians(55), 0, math.radians(-50)))

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 420
    scene.render.resolution_y = 560
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"


def bone_delta(human_bone_name, world_delta):
    rest = pose_bones[bone_names[human_bone_name]].bone.matrix_local.to_quaternion()
    return rest.inverted() @ world_delta @ rest


def set_rotation(human_bone_name, frame, world_delta):
    bone = pose_bones[bone_names[human_bone_name]]
    bone.rotation_mode = "QUATERNION"
    bone.rotation_quaternion = bone_delta(human_bone_name, world_delta)
    bone.keyframe_insert("rotation_quaternion", frame=frame)


def set_hips_location(frame, x, y, z):
    hips = pose_bones[bone_names["hips"]]
    hips.location = Vector((x, y, z))
    hips.keyframe_insert("location", frame=frame)


def direction_delta(human_bone_name, target_direction, roll_degrees=0.0):
    rest = pose_bones[bone_names[human_bone_name]].bone.matrix_local.to_3x3()
    rest_direction = (rest @ Vector((0, 1, 0))).normalized()
    target = Vector(target_direction).normalized()
    align = rest_direction.rotation_difference(target)
    return Quaternion(target, roll_degrees * RAD) @ align


def set_expression(name, frame, value):
    expression = getattr(vrm1.expressions.preset, name)
    expression.preview = max(0.0, min(1.0, value))
    expression.keyframe_insert("preview", frame=frame)


def action_fcurves(action):
    if bpy.app.version < (4, 4):
        return list(action.fcurves)
    from bpy.types import ActionKeyframeStrip

    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            if not isinstance(strip, ActionKeyframeStrip):
                continue
            for slot in action.slots:
                channel_bag = strip.channelbag(slot)
                if channel_bag:
                    curves.extend(channel_bag.fcurves)
    return curves


def smooth_action(action):
    for curve in action_fcurves(action):
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = "BEZIER"
            keyframe.handle_left_type = "AUTO"
            keyframe.handle_right_type = "AUTO"


relaxed_arms = {
    "leftUpperArm": qy(90),
    "leftLowerArm": qx(8) @ qy(90),
    "leftHand": qx(4) @ qy(90),
    "rightUpperArm": qy(-90),
    "rightLowerArm": qx(8) @ qy(-90),
    "rightHand": qx(4) @ qy(-90),
}

thinking_right_arm = {
    "rightUpperArm": direction_delta("rightUpperArm", (-0.42, -0.63, -0.18), -18),
    "rightLowerArm": direction_delta("rightLowerArm", (0.48, -0.18, 0.86), 4),
    "rightHand": direction_delta("rightHand", (0.10, -0.08, 0.99), 28),
}

finger_curl = {}
for side, sign in (("left", 1), ("right", -1)):
    for finger in ("Index", "Middle", "Ring", "Little"):
        finger_curl[f"{side}{finger}Proximal"] = qy(sign * 8)
        finger_curl[f"{side}{finger}Intermediate"] = qy(sign * 14)
        finger_curl[f"{side}{finger}Distal"] = qy(sign * 12)
    finger_curl[f"{side}ThumbProximal"] = qx(-6 * sign) @ qz(8 * sign)
    finger_curl[f"{side}ThumbDistal"] = qy(10 * sign)


def animate_fingers(frame, thinking_amount=0.0):
    for human_bone_name, relaxed in finger_curl.items():
        if human_bone_name not in bone_names:
            continue
        target = relaxed
        if thinking_amount and human_bone_name.startswith("right"):
            target = scale_quaternion(relaxed, 0.45)
        set_rotation(
            human_bone_name,
            frame,
            relaxed.slerp(target, thinking_amount),
        )


def animate_relaxed_arms(frame):
    for human_bone_name, rotation in relaxed_arms.items():
        set_rotation(human_bone_name, frame, rotation)


def animate_breath(frame, period):
    phase = 2.0 * math.pi * frame / period
    set_rotation("spine", frame, qx(-0.8 * math.sin(phase)))
    set_rotation("chest", frame, qx(0.48 * math.sin(phase + 0.55)))
    set_rotation("upperChest", frame, qx(0.34 * math.sin(phase + 0.25)))


def build_clip(name, frames, animator, blinks, preview_frames):
    scene.frame_start = 0
    scene.frame_end = frames
    pose_action = bpy.data.actions.new(f"Haihe_{name}_Pose")
    expression_action = bpy.data.actions.new(f"Haihe_{name}_Expression")
    armature.animation_data_create().action = pose_action
    armature.data.animation_data_create().action = expression_action

    for frame in range(frames + 1):
        animator(frame, frames)
        set_expression("blink", frame, 0.0)

    for center in blinks:
        set_expression("blink", center - 1, 0.0)
        set_expression("blink", center, 1.0)
        set_expression("blink", center + 2, 0.0)

    smooth_action(pose_action)
    smooth_action(expression_action)

    if preview_dir:
        for frame in preview_frames:
            scene.frame_set(frame)
            scene.render.filepath = os.path.join(preview_dir, f"{name}_f{frame:03d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"RENDERED {name} frame {frame}")

    output_path = os.path.join(output_dir, f"haihegirl_{name}.vrma")
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    result = bpy.ops.export_scene.vrma(
        filepath=output_path,
        armature_object_name=armature.name,
    )
    if result != {"FINISHED"} or not os.path.exists(output_path):
        raise RuntimeError(f"Failed to export {output_path}: {result}")
    print(f"EXPORTED {output_path} ({os.path.getsize(output_path)} bytes)")


def animate_idle(frame, frames):
    phase = 2.0 * math.pi * frame / frames
    animate_relaxed_arms(frame)
    animate_fingers(frame)
    animate_breath(frame, frames / 2)
    set_hips_location(frame, 0.009 * math.sin(phase), 0, 0.003 * (1 - math.cos(phase)))
    set_rotation("hips", frame, qz(0.55 * math.sin(phase)))
    head = qz(1.8 * math.sin(phase)) @ qy(1.1 * math.sin(phase * 2 + 0.7)) @ qx(
        -0.7 * math.sin(phase + 0.3)
    )
    set_rotation("head", frame, head)
    set_rotation("neck", frame, scale_quaternion(head, 0.32))


def animate_thinking(frame, frames):
    phase = 2.0 * math.pi * frame / frames
    # Ease into the chin-rest pose, hold it, then return to the neutral loop point.
    amount = smoothstep(4, 24, frame) * (1.0 - smoothstep(frames - 24, frames - 4, frame))
    for human_bone_name in ("rightUpperArm", "rightLowerArm", "rightHand"):
        set_rotation(
            human_bone_name,
            frame,
            relaxed_arms[human_bone_name].slerp(thinking_right_arm[human_bone_name], amount),
        )
    for human_bone_name in ("leftUpperArm", "leftLowerArm", "leftHand"):
        set_rotation(human_bone_name, frame, relaxed_arms[human_bone_name])
    animate_fingers(frame, amount)
    animate_breath(frame, frames)
    set_hips_location(frame, 0.006 * math.sin(phase), 0, 0)
    set_rotation("hips", frame, qz(-0.8 * amount + 0.3 * math.sin(phase)))

    head = (
        qz(-5.5 * amount + 1.0 * math.sin(phase))
        @ qy(4.5 * amount + 0.8 * math.sin(phase * 2))
        @ qx(2.0 * amount - 1.2 * math.sin(phase))
    )
    set_rotation("head", frame, head)
    set_rotation("neck", frame, scale_quaternion(head, 0.42))
    set_rotation(
        "chest",
        frame,
        qz(-1.8 * amount) @ qx(0.35 * math.sin(phase + 0.55)),
    )
    set_rotation("upperChest", frame, qz(-1.0 * amount))


build_clip("idle_6s", 180, animate_idle, (78, 151), (0, 45, 90, 135, 180))
build_clip("thinking_4s", 120, animate_thinking, (64,), (0, 20, 48, 72, 100, 120))
print("DONE")
