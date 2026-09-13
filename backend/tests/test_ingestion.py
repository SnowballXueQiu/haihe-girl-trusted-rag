import hashlib
import json
from pathlib import Path

from backend.app.ingestion import _extract_markdown, load_corpus


def test_markdown_page_headings_become_citation_pages(tmp_path: Path) -> None:
    reviewed = tmp_path / "reviewed.md"
    reviewed.write_text("# 第1页\n第一页内容。\n# 第3页\n第三页内容。\n", encoding="utf-8")

    units = _extract_markdown(reviewed)

    assert [(page, section) for page, section, _ in units] == [
        (1, "第1页"),
        (3, "第3页"),
    ]


def test_pdf_can_use_reviewed_text_without_losing_original_hash(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    knowledge_dir = project_root / "knowledge"
    source_dir = project_root / "sources"
    knowledge_dir.mkdir(parents=True)
    source_dir.mkdir()
    pdf_bytes = b"original-pdf-bytes"
    (source_dir / "scan.pdf").write_bytes(pdf_bytes)
    (knowledge_dir / "reviewed.md").write_text(
        "# 第1页\n经过人工核对的扫描页内容。\n",
        encoding="utf-8",
    )
    manifest = {
        "sources": [
            {
                "id": "scan",
                "title": "扫描资料",
                "publisher": "测试",
                "topic": "风筝魏",
                "type": "pdf",
                "path": "sources/scan.pdf",
                "text_path": "knowledge/reviewed.md",
            }
        ]
    }
    manifest_path = knowledge_dir / "sources.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    sources, chunks = load_corpus(manifest_path)

    assert sources[0].sha256 == hashlib.sha256(pdf_bytes).hexdigest()
    assert chunks[0].page == 1
    assert "人工核对" in chunks[0].text
