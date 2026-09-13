from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .embeddings import create_embedding_provider
from .generation import create_chat_provider, generate_grounded_answer
from .models import QueryRequest, SpeechRequest
from .retrieval import Retriever, to_citations
from .store import KnowledgeStore
from .tts import SpeechSynthesisError, synthesize_dashscope


REFUSAL_TEXT = "当前知识库没有足够依据，我不会凭空补充。你可以问我泥人张、风筝魏、海河文化、天津海棠，或我的角色设计。"

settings = get_settings()
app = FastAPI(title="海河少女可信 RAG 虚拟主播", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

store = KnowledgeStore(settings.rag_index_path)
speech_cache: dict[str, tuple[float, str]] = {}


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/api/health")
async def health() -> dict:
    metadata = store.index_metadata()
    index_status = _index_status(metadata)
    local_models = await _ollama_models() if (
        settings.generation_provider == "local" or settings.embedding_provider == "local"
    ) else set()
    model_ready = (
        settings.ollama_chat_model in local_models
        if settings.generation_provider == "local"
        else bool(settings.dashscope_api_key and settings.dashscope_workspace_id)
    )
    embedding_ready = (
        settings.ollama_embedding_model in local_models
        if settings.embedding_provider == "local"
        else bool(settings.dashscope_api_key and settings.dashscope_workspace_id)
    )
    speech_ready = bool(
        settings.tts_provider.lower() == "dashscope"
        and settings.dashscope_api_key
        and settings.dashscope_http_base_url
        and settings.dashscope_tts_model
        and settings.dashscope_tts_voice
    )
    vrm_ready = Path("frontend/public/models/haihe-girl.vrm").exists()
    return {
        "status": index_status,
        "generation_provider": settings.generation_provider,
        "embedding_provider": settings.embedding_provider,
        "tts_provider": settings.tts_provider,
        "index": metadata,
        "model_ready": model_ready,
        "embedding_ready": embedding_ready,
        "speech_ready": speech_ready,
        "vrm_ready": vrm_ready,
        "demo_ready": index_status == "ready" and model_ready and embedding_ready and speech_ready and vrm_ready,
    }


async def _ollama_models() -> set[str]:
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
        return {
            str(model.get("name") or model.get("model"))
            for model in response.json().get("models", [])
        }
    except (httpx.HTTPError, ValueError, TypeError):
        return set()


def _index_status(metadata: dict[str, str]) -> str:
    if not store.exists:
        return "index_missing"
    expected_provider = "ollama" if settings.embedding_provider == "local" else settings.embedding_provider
    expected_model = (
        settings.ollama_embedding_model
        if settings.embedding_provider == "local"
        else settings.dashscope_embedding_model
    )
    if (
        metadata.get("embedding_provider") != expected_provider
        or metadata.get("embedding_model") != expected_model
    ):
        return "index_mismatch"
    return "ready"


@app.post("/api/query")
async def query(request: QueryRequest) -> StreamingResponse:
    async def events():
        if not store.exists:
            yield _sse("error", {"message": "知识索引尚未建立，请先运行构建索引命令。"})
            return
        if _index_status(store.index_metadata()) != "ready":
            yield _sse("error", {"message": "知识索引与当前向量配置不匹配，请重新构建索引。"})
            return
        try:
            yield _sse("status", {"stage": "retrieving", "label": "正在检索可信资料"})
            embedding_provider = create_embedding_provider(settings)
            retriever = Retriever(store, embedding_provider, settings)
            results, sufficient, reason = await retriever.retrieve(request.question)
            citations = to_citations(results)
            yield _sse(
                "evidence",
                {"citations": [item.model_dump() for item in citations], "sufficient": sufficient},
            )
            if not sufficient:
                yield _sse("status", {"stage": "refused", "label": "证据不足，已停止生成"})
                yield _sse(
                    "final",
                    {
                        "answer": REFUSAL_TEXT,
                        "refused": True,
                        "reason": reason,
                        "citations": [],
                        "speech_token": None,
                    },
                )
                return

            yield _sse("status", {"stage": "generating", "label": "正在依据证据组织回答"})
            chat_provider = create_chat_provider(settings)
            answer = None
            last_generation_error: Exception | None = None
            for _ in range(settings.generation_max_attempts):
                try:
                    candidate = await generate_grounded_answer(
                        request.question,
                        results,
                        chat_provider,
                        settings.strict_grounding_verification,
                    )
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    last_generation_error = exc
                    continue
                answer = candidate
                if not candidate.refusal and candidate.text:
                    break
            if answer is None:
                raise RuntimeError("生成服务未返回可校验结果") from last_generation_error
            if answer.refusal or not answer.text:
                yield _sse("status", {"stage": "refused", "label": "回答未通过证据校验"})
                yield _sse(
                    "final",
                    {
                        "answer": REFUSAL_TEXT,
                        "refused": True,
                        "reason": answer.refusal_reason,
                        "citations": [],
                        "speech_token": None,
                    },
                )
                return

            used_ids = {cid for segment in answer.segments for cid in segment.citation_ids}
            used_citations = [item for item in citations if item.chunk_id in used_ids]
            yield _sse("status", {"stage": "verified", "label": "引用校验通过"})
            for offset in range(0, len(answer.text), 18):
                yield _sse("token", {"text": answer.text[offset : offset + 18]})
                await asyncio.sleep(0.018)
            speech_token = uuid.uuid4().hex
            speech_cache[speech_token] = (time.time() + 300, answer.text)
            yield _sse(
                "final",
                {
                    "answer": answer.text,
                    "refused": False,
                    "reason": None,
                    "citations": [item.model_dump() for item in used_citations],
                    "speech_token": speech_token,
                },
            )
        except Exception:
            # Do not return provider URLs, workspace identifiers, signed audio
            # links, or raw upstream payloads to the browser.
            yield _sse(
                "error",
                {
                    "message": (
                        "可信问答服务暂不可用，已停止回答。"
                        "请检查网络、余额与业务空间配置。"
                    )
                },
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/speech")
async def speech(request: SpeechRequest) -> Response:
    now = time.time()
    expired = [token for token, (deadline, _) in speech_cache.items() if deadline < now]
    for token in expired:
        speech_cache.pop(token, None)
    cached = speech_cache.get(request.speech_token)
    if not cached:
        raise HTTPException(status_code=403, detail="回答尚未通过校验或播报令牌已过期")
    _, text = cached
    try:
        audio = await asyncio.to_thread(synthesize_dashscope, text, settings)
    except SpeechSynthesisError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    speech_cache.pop(request.speech_token, None)
    return Response(content=audio.data, media_type=audio.media_type)


@app.get("/api/sources/{source_id}")
async def source(source_id: str, chunk_id: str | None = None):  # type: ignore[no-untyped-def]
    target = store.source_path(source_id)
    if not target:
        raise HTTPException(status_code=404, detail="来源不存在")
    path, url = target
    if path.exists():
        return FileResponse(path)
    if url:
        return RedirectResponse(url)
    preview = store.source_preview(source_id, chunk_id)
    if preview:
        page = f"第 {preview['page']} 页" if preview["page"] else "未分页"
        return PlainTextResponse(
            "\n".join(
                [
                    str(preview["title"]),
                    f"发布者：{preview['publisher']}",
                    f"位置：{page}",
                    f"证据块：{preview['chunk_id']}",
                    "",
                    str(preview["text"]),
                    "",
                    f"使用说明：{preview['license_note']}",
                    "为避免未经授权再分发，参赛包仅展示本轮已审核引用摘录，不附论文全文。",
                ]
            )
        )
    raise HTTPException(status_code=404, detail="来源文件不可用")


frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
