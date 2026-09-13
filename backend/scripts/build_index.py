from __future__ import annotations

import asyncio

from backend.app.config import get_settings
from backend.app.embeddings import create_embedding_provider
from backend.app.ingestion import load_corpus
from backend.app.store import build_store


async def main() -> None:
    settings = get_settings()
    sources, chunks = load_corpus(settings.knowledge_manifest)
    provider = create_embedding_provider(settings)
    print(f"正在构建索引：{len(sources)} 个来源，{len(chunks)} 个知识块")
    print(f"向量模型：{provider.name}/{provider.model}")
    await build_store(settings.rag_index_path, sources, chunks, provider)
    print(f"索引已写入：{settings.rag_index_path}")


if __name__ == "__main__":
    asyncio.run(main())
