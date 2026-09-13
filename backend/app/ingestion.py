from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from .models import ChunkRecord, SourceRecord
from .text import chunk_text, lexicalize, normalize_text


def load_corpus(manifest_path: Path) -> tuple[list[SourceRecord], list[ChunkRecord]]:
    manifest_path = manifest_path.resolve()
    project_root = manifest_path.parent.parent
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources: list[SourceRecord] = []
    chunks: list[ChunkRecord] = []

    for item in payload["sources"]:
        path = (project_root / item["path"]).resolve()
        if not path.exists():
            raise FileNotFoundError(f"知识源不存在: {path}")
        extraction_path = None
        if item.get("text_path"):
            extraction_path = (project_root / item["text_path"]).resolve()
            if not extraction_path.exists():
                raise FileNotFoundError(f"审核文本不存在: {extraction_path}")
        source = SourceRecord(
            source_id=item["id"],
            title=item["title"],
            publisher=item["publisher"],
            topic=item["topic"],
            source_type=item["type"],
            path=path,
            url=item.get("url"),
            license_note=item.get("license_note", "仅用于教学竞赛中的事实检索与引用"),
            sha256=_sha256(path),
        )
        sources.append(source)
        chunks.extend(_extract_source(source, extraction_path))
    return sources, chunks


def _extract_source(
    source: SourceRecord,
    extraction_path: Path | None = None,
) -> list[ChunkRecord]:
    if extraction_path is not None:
        units = _extract_markdown(extraction_path)
    elif source.source_type == "pdf":
        units = _extract_pdf(source.path)
    elif source.source_type == "docx":
        units = _extract_docx(source.path)
    elif source.source_type == "markdown":
        units = _extract_markdown(source.path)
    else:
        raise ValueError(f"不支持的知识源类型: {source.source_type}")

    records: list[ChunkRecord] = []
    serial = 0
    for page, section, text in units:
        for part in chunk_text(text):
            serial += 1
            records.append(
                ChunkRecord(
                    chunk_id=f"{source.source_id}-{serial:04d}",
                    source_id=source.source_id,
                    title=source.title,
                    publisher=source.publisher,
                    topic=source.topic,
                    text=part,
                    search_text=lexicalize(part),
                    page=page,
                    section=section,
                    url=source.url,
                )
            )
    return records


def _extract_pdf(path: Path) -> list[tuple[int | None, str | None, str]]:
    reader = PdfReader(str(path))
    return [
        (index, f"第{index}页", normalize_text(page.extract_text() or ""))
        for index, page in enumerate(reader.pages, 1)
        if normalize_text(page.extract_text() or "")
    ]


def _extract_docx(path: Path) -> list[tuple[int | None, str | None, str]]:
    document = Document(str(path))
    units: list[tuple[int | None, str | None, str]] = []
    section = "正文"
    buffer: list[str] = []
    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            continue
        if paragraph.style and paragraph.style.name.lower().startswith("heading"):
            if buffer:
                units.append((None, section, "\n".join(buffer)))
                buffer = []
            section = text
        else:
            buffer.append(text)
    if buffer:
        units.append((None, section, "\n".join(buffer)))
    return units


def _extract_markdown(path: Path) -> list[tuple[int | None, str | None, str]]:
    units: list[tuple[int | None, str | None, str]] = []
    section = "正文"
    page: int | None = None
    buffer: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            if buffer:
                units.append((page, section, "\n".join(buffer)))
                buffer = []
            section = line.lstrip("# ").strip()
            page_match = re.fullmatch(r"第\s*(\d+)\s*页", section)
            if page_match:
                page = int(page_match.group(1))
        elif line.strip():
            buffer.append(line.strip())
    if buffer:
        units.append((page, section, "\n".join(buffer)))
    return units


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
