from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from .embeddings import EmbeddingProvider
from .models import ChunkRecord, RetrievedChunk, SourceRecord
from .text import lexical_tokens, token_overlap


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  publisher TEXT NOT NULL,
  topic TEXT NOT NULL,
  source_type TEXT NOT NULL,
  path TEXT NOT NULL,
  url TEXT,
  license_note TEXT NOT NULL,
  sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  title TEXT NOT NULL,
  publisher TEXT NOT NULL,
  topic TEXT NOT NULL,
  text TEXT NOT NULL,
  search_text TEXT NOT NULL,
  page INTEGER,
  section TEXT,
  url TEXT,
  embedding BLOB,
  embedding_dim INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED,
  search_text,
  title,
  tokenize='unicode61'
);
"""


class KnowledgeStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def index_metadata(self) -> dict[str, str]:
        if not self.exists:
            return {}
        try:
            with self.connect() as connection:
                return {
                    row["key"]: row["value"]
                    for row in connection.execute("SELECT key, value FROM metadata")
                }
        except sqlite3.DatabaseError:
            return {}

    def lexical_search(self, query: str, limit: int = 12) -> list[RetrievedChunk]:
        tokens = lexical_tokens(query)
        if not tokens or not self.exists:
            return []
        expression = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:40])
        sql = """
            SELECT c.*, bm25(chunks_fts) AS fts_score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
            ORDER BY fts_score ASC
            LIMIT ?
        """
        with self.connect() as connection:
            rows = connection.execute(sql, (expression, limit)).fetchall()
        return [
            RetrievedChunk(
                chunk=_row_to_chunk(row),
                lexical_overlap=token_overlap(query, row["text"]),
                retrieval_paths={"lexical"},
            )
            for row in rows
        ]

    def vector_search(self, vector: list[float], limit: int = 12) -> list[RetrievedChunk]:
        if not self.exists:
            return []
        query = np.asarray(vector, dtype=np.float32)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE embedding IS NOT NULL AND embedding_dim = ?",
                (len(vector),),
            ).fetchall()
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            candidate = np.frombuffer(row["embedding"], dtype=np.float32)
            score = float(np.dot(query, candidate))
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(
                chunk=_row_to_chunk(row),
                vector_score=score,
                retrieval_paths={"vector"},
            )
            for score, row in scored[:limit]
        ]

    def source_path(self, source_id: str) -> tuple[Path, str | None] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT path, url FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
        if not row:
            return None
        path = Path(row["path"])
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve(), row["url"]

    def source_preview(self, source_id: str, chunk_id: str | None = None) -> dict[str, object] | None:
        """Return one indexed excerpt when the distributable omits a copyrighted source file."""
        with self.connect() as connection:
            source = connection.execute(
                """SELECT source_id, title, publisher, license_note
                   FROM sources WHERE source_id = ?""",
                (source_id,),
            ).fetchone()
            if not source:
                return None
            if chunk_id:
                chunk = connection.execute(
                    """SELECT chunk_id, text, page FROM chunks
                       WHERE source_id = ? AND chunk_id = ?""",
                    (source_id, chunk_id),
                ).fetchone()
            else:
                chunk = connection.execute(
                    """SELECT chunk_id, text, page FROM chunks
                       WHERE source_id = ? ORDER BY chunk_id LIMIT 1""",
                    (source_id,),
                ).fetchone()
        if not chunk:
            return None
        return {
            "source_id": source["source_id"],
            "title": source["title"],
            "publisher": source["publisher"],
            "license_note": source["license_note"],
            "chunk_id": chunk["chunk_id"],
            "page": chunk["page"],
            "text": chunk["text"],
        }


async def build_store(
    path: Path,
    sources: list[SourceRecord],
    chunks: list[ChunkRecord],
    provider: EmbeddingProvider,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".building")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            [
                ("embedding_provider", provider.name),
                ("embedding_model", provider.model),
                ("chunk_count", str(len(chunks))),
                ("source_count", str(len(sources))),
            ],
        )
        connection.executemany(
            """INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    item.source_id,
                    item.title,
                    item.publisher,
                    item.topic,
                    item.source_type,
                    _portable_path(item.path),
                    item.url,
                    item.license_note,
                    item.sha256,
                )
                for item in sources
            ],
        )
        batch_size = 20
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = await provider.embed([item.text for item in batch])
            for item, vector in zip(batch, vectors, strict=True):
                item.embedding = vector
                array = np.asarray(vector, dtype=np.float32)
                connection.execute(
                    """INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.chunk_id,
                        item.source_id,
                        item.title,
                        item.publisher,
                        item.topic,
                        item.text,
                        item.search_text,
                        item.page,
                        item.section,
                        item.url,
                        array.tobytes(),
                        len(vector),
                    ),
                )
                connection.execute(
                    "INSERT INTO chunks_fts(chunk_id, search_text, title) VALUES (?, ?, ?)",
                    (item.chunk_id, item.search_text, item.title),
                )
        connection.commit()
    finally:
        connection.close()
    temporary.replace(path)


def _row_to_chunk(row: sqlite3.Row) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=row["chunk_id"],
        source_id=row["source_id"],
        title=row["title"],
        publisher=row["publisher"],
        topic=row["topic"],
        text=row["text"],
        search_text=row["search_text"],
        page=row["page"],
        section=row["section"],
        url=row["url"],
    )


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path.resolve())
