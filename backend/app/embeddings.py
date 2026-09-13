from __future__ import annotations

import asyncio
import hashlib
import math
from abc import ABC, abstractmethod

import httpx
import numpy as np

from .config import Settings
from .text import lexical_tokens


class EmbeddingProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic, network-free provider used only by unit tests."""

    name = "hash"
    model = "hash-bigram-v1"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = np.zeros(self.dimensions, dtype=np.float32)
            for token in lexical_tokens(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "little") % self.dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign
            norm = float(np.linalg.norm(vector))
            if norm:
                vector /= norm
            vectors.append(vector.tolist())
        return vectors


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
        return [_normalize(vector) for vector in payload["embeddings"]]


class DashScopeEmbeddingProvider(EmbeddingProvider):
    name = "dashscope"

    def __init__(self, settings: Settings) -> None:
        if not settings.dashscope_api_key or not settings.dashscope_openai_base_url:
            raise RuntimeError("DASHSCOPE_API_KEY 和 DASHSCOPE_WORKSPACE_ID 尚未配置")
        self.base_url = settings.dashscope_openai_base_url.rstrip("/")
        self.api_key = settings.dashscope_api_key
        self.workspace_id = settings.dashscope_workspace_id
        self.model = settings.dashscope_embedding_model
        self.dimensions = settings.dashscope_embedding_dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        async with httpx.AsyncClient(timeout=180.0) as client:
            for start in range(0, len(texts), 20):
                headers = {"Authorization": f"Bearer {self.api_key}"}
                if self.workspace_id:
                    headers["X-DashScope-WorkSpace"] = self.workspace_id
                for attempt in range(4):
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers=headers,
                        json={
                            "model": self.model,
                            "input": texts[start : start + 20],
                            "dimensions": self.dimensions,
                        },
                    )
                    if response.status_code not in {403, 429, 500, 502, 503, 504}:
                        response.raise_for_status()
                        break
                    if attempt == 3:
                        response.raise_for_status()
                    await asyncio.sleep(0.5 * (2**attempt))
                data = sorted(response.json()["data"], key=lambda item: item["index"])
                result.extend(_normalize(item["embedding"]) for item in data)
        return result


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider == "dashscope":
        return DashScopeEmbeddingProvider(settings)
    if provider == "hash":
        return HashEmbeddingProvider()
    if provider == "local":
        return OllamaEmbeddingProvider(settings)
    raise ValueError(f"不支持的向量提供方: {settings.embedding_provider}")


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]
