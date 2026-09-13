from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import Settings


class SpeechSynthesisError(RuntimeError):
    pass


@dataclass(slots=True)
class SpeechAudio:
    data: bytes
    media_type: str


_MAX_TEXT_LENGTH = 600
_MAX_AUDIO_BYTES = 15 * 1024 * 1024


def _safe_audio_url(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise SpeechSynthesisError("语音服务没有返回音频地址")
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        hostname == "aliyuncs.com" or hostname.endswith(".aliyuncs.com")
    ):
        raise SpeechSynthesisError("语音服务返回了不可信的音频地址")
    return value


def _content_type(response: httpx.Response) -> str:
    declared = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if declared in {"audio/x-wav", "audio/wave"}:
        return "audio/wav"
    if declared == "audio/mp3":
        return "audio/mpeg"
    if declared.startswith("audio/"):
        return declared
    data = response.content
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"ID3") or data[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return "audio/mpeg"
    return "application/octet-stream"


def synthesize_dashscope(text: str, settings: Settings) -> SpeechAudio:
    if settings.tts_provider.lower() != "dashscope":
        raise SpeechSynthesisError("当前未启用百炼语音服务")
    if not settings.dashscope_api_key:
        raise SpeechSynthesisError("DASHSCOPE_API_KEY 尚未配置")
    base_url = settings.dashscope_http_base_url
    if not base_url:
        raise SpeechSynthesisError("百炼语音服务地址尚未配置")
    clean_text = text.strip()
    if not clean_text:
        raise SpeechSynthesisError("待播报文本为空")
    if len(clean_text) > _MAX_TEXT_LENGTH:
        raise SpeechSynthesisError(f"待播报文本超过 {_MAX_TEXT_LENGTH} 字符")

    endpoint = f"{base_url}/services/aigc/multimodal-generation/generation"
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    if settings.dashscope_workspace_id:
        headers["X-DashScope-WorkSpace"] = settings.dashscope_workspace_id
    payload = {
        "model": settings.dashscope_tts_model,
        "input": {
            "text": clean_text,
            "voice": settings.dashscope_tts_voice,
            "language_type": settings.dashscope_tts_language,
        },
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0), follow_redirects=True) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            audio_url = _safe_audio_url(
                body.get("output", {}).get("audio", {}).get("url")
                if isinstance(body, dict)
                else None
            )
            audio_response = client.get(audio_url)
            audio_response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpeechSynthesisError("百炼语音合成超时，请重试") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {401, 403}:
            message = "百炼语音鉴权失败，请检查密钥、业务空间和模型权限"
        elif status == 429:
            message = "百炼语音请求过于频繁，请稍后重试"
        else:
            message = f"百炼语音服务请求失败（HTTP {status}）"
        raise SpeechSynthesisError(message) from exc
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SpeechSynthesisError("百炼语音服务返回格式异常") from exc
    except httpx.HTTPError as exc:
        raise SpeechSynthesisError("无法连接百炼语音服务") from exc

    declared_size = audio_response.headers.get("content-length")
    if declared_size and declared_size.isdigit() and int(declared_size) > _MAX_AUDIO_BYTES:
        raise SpeechSynthesisError("语音服务返回的音频超过大小限制")
    if not audio_response.content:
        raise SpeechSynthesisError("语音服务没有返回音频")
    if len(audio_response.content) > _MAX_AUDIO_BYTES:
        raise SpeechSynthesisError("语音服务返回的音频超过大小限制")
    media_type = _content_type(audio_response)
    if media_type == "application/octet-stream":
        raise SpeechSynthesisError("语音服务返回的文件不是可识别音频")
    return SpeechAudio(audio_response.content, media_type)


def _pcm_to_wav(pcm: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(pcm)
    return output.getvalue()
