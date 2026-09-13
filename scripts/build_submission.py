from __future__ import annotations

import argparse
import re
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INCLUDE = [
    "backend",
    "frontend",
    "knowledge",
    "docs",
    "submission_materials",
    ".data/index.sqlite",
    ".data/retrieval-evaluation.json",
    ".data/end-to-end-smoke.json",
    "output/pdf/海河少女可信RAG虚拟主播系统设计论文.pdf",
    "output/pdf/AI工具使用声明.pdf",
    "output/pdf/人机协作过程说明.pdf",
    "output/pdf/运行与操作说明.pdf",
    "paper/main.tex",
    "paper/references.bib",
    "paper/README.md",
    "output/video/海河少女功能演示.mp4",
    "海河少女/model01.vroid",
    "海河少女/人物设计过程/3cdfb743e2d76f972399badb1bd1d1c1.png",
    "海河少女/人物设计过程/87d8ef17ef933f6209dd43ff18144453.png",
    "海河少女/人物设计过程/8fc0881b93edd0a068ebc5579a076749.png",
    "海河少女/人物设计过程/e8b7fd390115ca5bdf1cc364c031aee5.png",
    "海河少女/海河少女设计思路.docx",
    "海河少女/角色档案.docx",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    ".env.example",
    "pyproject.toml",
    "uv.lock",
    "scripts",
]
EXCLUDED_PARTS = {"node_modules", "__pycache__", ".pytest_cache"}
SECRET_PATTERN = re.compile(rb"sk-[A-Za-z0-9._-]{16,}")


def files() -> list[Path]:
    result: list[Path] = []
    for relative in INCLUDE:
        target = ROOT / relative
        if target.is_file():
            result.append(target)
        elif target.is_dir():
            result.extend(
                path
                for path in target.rglob("*")
                if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDED_PARTS)
            )
    return sorted(set(result))


def main() -> None:
    parser = argparse.ArgumentParser(description="生成学校统一提交的参赛包")
    parser.add_argument("--school", default="待填写学校", help="学校全称")
    parser.add_argument(
        "--draft",
        action="store_true",
        help="允许生成缺少签字材料、正式视频或百炼配置的内部草稿包",
    )
    args = parser.parse_args()
    if not args.draft:
        check = subprocess.run([str(ROOT / "scripts" / "check_submission.sh")], cwd=ROOT)
        if check.returncode:
            raise SystemExit("终检未通过；如仅需内部核对，请显式使用 --draft。")
    safe_school = re.sub(r"[\\/:*?\"<>|]", "_", args.school.strip()) or "待填写学校"
    draft_suffix = "-草稿" if args.draft else ""
    output = ROOT / "output" / (
        f"{safe_school}+海河少女基于可信RAG的天津文化AI虚拟主播系统{draft_suffix}.zip"
    )
    selected = files()
    required = [ROOT / ".data/index.sqlite", ROOT / "frontend/dist/index.html"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"缺少可运行文件：{', '.join(missing)}")
    for path in selected:
        if SECRET_PATTERN.search(path.read_bytes()):
            raise SystemExit(f"疑似密钥，拒绝打包：{path.relative_to(ROOT)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in selected:
            archive.write(path, path.relative_to(ROOT))
    size = output.stat().st_size
    if size > 500 * 1024 * 1024:
        output.unlink()
        raise SystemExit("参赛包超过500MB，已删除失败产物")
    print(f"参赛包：{output}")
    print(f"大小：{size / 1024 / 1024:.1f} MB，文件数：{len(selected)}")
    if args.draft:
        print("提示：这是内部草稿包，不得代替通过终检的学校正式提交包。")


if __name__ == "__main__":
    main()
