from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    generation_provider: str = "local"
    generation_max_attempts: int = Field(default=2, ge=1, le=3)
    embedding_provider: str = "local"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "qwen3.5:27b"
    ollama_embedding_model: str = "qwen3-embedding:4b"

    dashscope_api_key: str = ""
    dashscope_workspace_id: str = ""
    dashscope_region: str = "ap-southeast-1"
    dashscope_api_host: str = ""
    dashscope_compatible_base_url: str = ""
    dashscope_native_base_url: str = ""
    dashscope_chat_model: str = "qwen3.7-flash-2026-07-15"
    dashscope_embedding_model: str = "qwen3.7-text-embedding"
    dashscope_embedding_dimensions: int = 1024

    tts_provider: str = "dashscope"
    dashscope_tts_model: str = "qwen3-tts-flash-2025-11-27"
    dashscope_tts_voice: str = "Momo"
    dashscope_tts_language: str = "Chinese"

    knowledge_manifest: Path = Path("knowledge/sources.json")
    rag_index_path: Path = Path(".data/index.sqlite")
    retrieval_top_k: int = Field(default=6, ge=1, le=12)
    retrieval_vector_threshold: float = Field(default=0.52, ge=-1.0, le=1.0)
    retrieval_lexical_threshold: float = Field(default=0.08, ge=0.0, le=1.0)
    retrieval_allow_lexical_fallback: bool = False
    strict_grounding_verification: bool = True

    @property
    def dashscope_openai_base_url(self) -> str:
        if self.dashscope_compatible_base_url:
            return self.dashscope_compatible_base_url.rstrip("/")
        if self.dashscope_api_host:
            return f"https://{self.dashscope_api_host.rstrip('/')}/compatible-mode/v1"
        if not self.dashscope_workspace_id or not self.dashscope_region:
            return ""
        return (
            f"https://{self.dashscope_workspace_id}.{self.dashscope_region}.maas.aliyuncs.com"
            "/compatible-mode/v1"
        )

    @property
    def dashscope_http_base_url(self) -> str:
        if self.dashscope_native_base_url:
            return self.dashscope_native_base_url.rstrip("/")
        if self.dashscope_api_host:
            return f"https://{self.dashscope_api_host.rstrip('/')}/api/v1"
        if not self.dashscope_workspace_id or not self.dashscope_region:
            return ""
        return (
            f"https://{self.dashscope_workspace_id}.{self.dashscope_region}.maas.aliyuncs.com"
            "/api/v1"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
