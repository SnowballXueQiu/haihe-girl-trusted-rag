import json
import io
import wave

import httpx
import pytest

from backend.app import tts
from backend.app.config import Settings
from backend.app.tts import SpeechSynthesisError, _pcm_to_wav, synthesize_dashscope


def test_pcm_is_wrapped_as_24khz_mono_wav() -> None:
    payload = _pcm_to_wav(b"\0\0" * 240)
    with wave.open(io.BytesIO(payload), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24000
        assert audio.getnframes() == 240


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        dashscope_workspace_id="ws-test",
        dashscope_region="ap-southeast-1",
        dashscope_native_base_url="https://ws-test.ap-southeast-1.maas.aliyuncs.com/api/v1",
        dashscope_tts_model="qwen3-tts-flash-2025-11-27",
        dashscope_tts_voice="Momo",
        dashscope_tts_language="Chinese",
    )


def test_workspace_http_tts_downloads_audio(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    wav = _pcm_to_wav(b"\0\0" * 240)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert str(request.url) == (
                "https://ws-test.ap-southeast-1.maas.aliyuncs.com/api/v1/"
                "services/aigc/multimodal-generation/generation"
            )
            assert request.headers["authorization"] == "Bearer test-key"
            assert request.headers["x-dashscope-workspace"] == "ws-test"
            assert json.loads(request.content) == {
                "model": "qwen3-tts-flash-2025-11-27",
                "input": {
                    "text": "大家好，我是海河少女。",
                    "voice": "Momo",
                    "language_type": "Chinese",
                },
            }
            return httpx.Response(
                200,
                json={"output": {"audio": {"url": "https://audio.aliyuncs.com/result.wav"}}},
            )
        return httpx.Response(200, content=wav, headers={"Content-Type": "audio/wav"})

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        tts.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    audio = synthesize_dashscope("大家好，我是海河少女。", _settings())
    assert audio.data == wav
    assert audio.media_type == "audio/wav"
    assert len(requests) == 2


def test_workspace_http_tts_rejects_untrusted_audio_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"output": {"audio": {"url": "https://example.com/untrusted.wav"}}},
        )

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        tts.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    with pytest.raises(SpeechSynthesisError, match="不可信"):
        synthesize_dashscope("测试", _settings())


def test_singapore_workspace_urls_are_not_hardcoded_to_beijing() -> None:
    settings = Settings(
        _env_file=None,
        dashscope_workspace_id="ws-test",
        dashscope_region="ap-southeast-1",
    )
    assert settings.dashscope_openai_base_url == (
        "https://ws-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.dashscope_http_base_url == (
        "https://ws-test.ap-southeast-1.maas.aliyuncs.com/api/v1"
    )
