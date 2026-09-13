from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: str = Field(default="demo", min_length=1, max_length=80)


class SpeechRequest(BaseModel):
    speech_token: str = Field(min_length=8, max_length=100)


class Citation(BaseModel):
    source_id: str
    chunk_id: str
    title: str
    publisher: str
    page: int | None = None
    excerpt: str
    url: str | None = None


class AnswerSegment(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    citation_ids: list[str] = Field(min_length=1)


class GroundedAnswer(BaseModel):
    segments: list[AnswerSegment] = Field(default_factory=list)
    refusal: bool = False
    refusal_reason: str | None = None

    @property
    def text(self) -> str:
        return "".join(segment.text for segment in self.segments).strip()


@dataclass(slots=True)
class SourceRecord:
    source_id: str
    title: str
    publisher: str
    topic: str
    source_type: str
    path: Path
    url: str | None
    license_note: str
    sha256: str


@dataclass(slots=True)
class ChunkRecord:
    chunk_id: str
    source_id: str
    title: str
    publisher: str
    topic: str
    text: str
    search_text: str
    page: int | None
    section: str | None
    url: str | None
    embedding: list[float] | None = None


@dataclass(slots=True)
class RetrievedChunk:
    chunk: ChunkRecord
    rank_score: float = 0.0
    vector_score: float | None = None
    lexical_overlap: float = 0.0
    retrieval_paths: set[str] = field(default_factory=set)


class RetrievalResult(BaseModel):
    sufficient: bool
    reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
