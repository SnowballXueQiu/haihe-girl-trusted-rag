import json

import httpx

from backend.app import embeddings
from backend.app.config import Settings
from backend.app.embeddings import DashScopeEmbeddingProvider


async def test_dashscope_embedding_retries_temporary_forbidden(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["x-dashscope-workspace"] == "ws-test"
        payload = json.loads(request.content)
        assert payload["dimensions"] == 2
        if attempts == 1:
            return httpx.Response(403, json={"code": "Arrearage"})
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [3.0, 4.0]}]},
        )

    async def no_sleep(delay: float) -> None:
        return None

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        embeddings.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(embeddings.asyncio, "sleep", no_sleep)
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        dashscope_workspace_id="ws-test",
        dashscope_compatible_base_url=(
            "https://ws-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
        ),
        dashscope_embedding_dimensions=2,
    )

    vectors = await DashScopeEmbeddingProvider(settings).embed(["海河"])
    assert attempts == 2
    assert vectors == [[0.6, 0.8]]
