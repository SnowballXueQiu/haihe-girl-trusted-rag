from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


JSON_CHUNK = 0x4E4F534A
REQUIRED_BONES = {"hips", "spine", "neck", "head", "leftEye", "rightEye"}


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("文件过短，不是有效 GLB/VRM")
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total_length != len(data):
        raise ValueError("GLB 文件头或长度无效")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != JSON_CHUNK or 20 + chunk_length > len(data):
        raise ValueError("找不到有效 GLB JSON 块")
    return json.loads(data[20 : 20 + chunk_length].decode("utf-8").rstrip(" \t\r\n\0"))


def validate(path: Path) -> tuple[list[str], list[str]]:
    gltf = read_glb(path)
    extensions = gltf.get("extensions", {})
    errors: list[str] = []
    notes: list[str] = []

    if "VRMC_vrm" in extensions:
        vrm = extensions["VRMC_vrm"]
        notes.append(f"VRM 版本：1.0（specVersion={vrm.get('specVersion', '未知')}）")
        human_bones = set(vrm.get("humanoid", {}).get("humanBones", {}))
        expressions = set(vrm.get("expressions", {}).get("preset", {}))
        meta = vrm.get("meta", {})
        if not meta.get("authors"):
            errors.append("VRM 1.0 meta.authors 未填写")
        if not meta.get("name"):
            errors.append("VRM 1.0 meta.name 未填写")
    elif "VRM" in extensions:
        vrm = extensions["VRM"]
        notes.append(f"VRM 版本：0.x（specVersion={vrm.get('specVersion', '未知')}）")
        human_bones = {
            item.get("bone")
            for item in vrm.get("humanoid", {}).get("humanBones", [])
            if item.get("bone")
        }
        groups = vrm.get("blendShapeMaster", {}).get("blendShapeGroups", [])
        expressions = {
            str(item.get("presetName") or item.get("name") or "").lower()
            for item in groups
        }
        meta = vrm.get("meta", {})
        if not meta.get("author"):
            errors.append("VRM 0.x meta.author 未填写")
        if not meta.get("title"):
            errors.append("VRM 0.x meta.title 未填写")
    else:
        return ["文件不包含 VRMC_vrm 或 VRM 扩展"], notes

    missing_bones = sorted(REQUIRED_BONES - human_bones)
    if missing_bones:
        errors.append("缺少骨骼：" + ", ".join(missing_bones))
    if "blink" not in expressions:
        errors.append("缺少 blink 眨眼表情")
    if not ({"aa", "a"} & expressions):
        errors.append("缺少 aa/A 口型表情")

    notes.append(f"文件大小：{path.stat().st_size / 1024 / 1024:.1f} MB")
    notes.append(f"已识别骨骼：{len(human_bones)}；预设表情：{len(expressions)}")
    return errors, notes


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/public/models/haihe-girl.vrm")
    if not path.exists():
        raise SystemExit(f"[缺失] {path}")
    try:
        errors, notes = validate(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[失败] {exc}") from exc
    for note in notes:
        print(f"[信息] {note}")
    if errors:
        for error in errors:
            print(f"[失败] {error}")
        raise SystemExit(1)
    print("[OK] VRM 结构、主要骨骼、眨眼、口型和基础作者信息验证通过。")


if __name__ == "__main__":
    main()
