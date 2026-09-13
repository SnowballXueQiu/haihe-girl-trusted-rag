from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import httpx

from .config import Settings
from .models import AnswerSegment, GroundedAnswer, RetrievedChunk
from .text import token_overlap


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citation_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "citation_ids"],
            },
        },
        "refusal": {"type": "boolean"},
        "refusal_reason": {"type": ["string", "null"]},
    },
    "required": ["segments", "refusal", "refusal_reason"],
}


SYSTEM_PROMPT = """你是“海河少女”，天津文化可信虚拟主播。你只依据本轮提供的证据回答。
规则：
1. 禁止使用模型记忆补充事实，禁止联网推测。
2. 每个事实段必须引用至少一个证据块 ID，且引用必须直接支持该段内容。
3. 将角色世界观创作设定与可考证历史事实清楚区分。
4. 证据不足时 refusal=true，不得勉强回答。
5. 语气亲切、自然、克制，回答控制在 100 至 220 个汉字；不添加证据没有明说的形容、结论或背景。
6. 证据块 ID 只写入 citation_ids 字段，text 字段不得出现任何引用标记，包括[1]、[2]。
7. 只输出符合给定结构的 JSON，不输出 Markdown 代码块。"""


class ChatProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        raise NotImplementedError


class OllamaChatProvider(ChatProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_chat_model

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    # Qwen 3.5 enables long hidden reasoning by default.  Structured
                    # RAG generation and the independent verifier do not need it,
                    # and disabling it keeps the live demo responsive.
                    "think": False,
                    "format": schema,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "options": {"temperature": 0.0, "num_ctx": 16384, "num_predict": 700},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
        return _parse_json(content)


class DashScopeChatProvider(ChatProvider):
    name = "dashscope"

    def __init__(self, settings: Settings) -> None:
        if not settings.dashscope_api_key or not settings.dashscope_openai_base_url:
            raise RuntimeError("DASHSCOPE_API_KEY 和 DASHSCOPE_WORKSPACE_ID 尚未配置")
        self.base_url = settings.dashscope_openai_base_url.rstrip("/")
        self.api_key = settings.dashscope_api_key
        self.workspace_id = settings.dashscope_workspace_id
        self.model = settings.dashscope_chat_model

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        grounded_system = (
            f"{system}\n\n输出的 JSON 必须严格符合以下 JSON Schema：\n{schema_text}"
        )
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.workspace_id:
            headers["X-DashScope-WorkSpace"] = self.workspace_id
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": grounded_system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.0,
                    "enable_thinking": False,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return _parse_json(content)


def create_chat_provider(settings: Settings) -> ChatProvider:
    if settings.generation_provider.lower() == "dashscope":
        return DashScopeChatProvider(settings)
    if settings.generation_provider.lower() == "local":
        return OllamaChatProvider(settings)
    raise ValueError(f"不支持的生成提供方: {settings.generation_provider}")


async def generate_grounded_answer(
    question: str,
    evidence: list[RetrievedChunk],
    provider: ChatProvider,
    strict_verification: bool,
) -> GroundedAnswer:
    evidence_text = "\n\n".join(
        f"[证据块 {item.chunk.chunk_id}]\n"
        f"来源：{item.chunk.title}；发布者：{item.chunk.publisher}；"
        f"页码：{item.chunk.page or '未分页'}\n{item.chunk.text}"
        for item in evidence
    )
    payload = await provider.complete_json(
        SYSTEM_PROMPT,
        f"用户问题：{question}\n\n只可使用以下证据：\n{evidence_text}",
        ANSWER_SCHEMA,
    )
    answer = GroundedAnswer.model_validate(payload)
    # Local models may redundantly render citation IDs inside prose. They are
    # already carried structurally in `citation_ids`; remove only that exact
    # marker form before numeric grounding and before text reaches UI or TTS.
    for segment in answer.segments:
        segment.text = re.sub(r"\s*\[证据块\s+[^\]]+\]", "", segment.text).strip()
        segment.text = re.sub(
            r"\s*(?:\[(?:\d+(?:\s*[-,，]\s*\d+)*)\]|"
            r"【(?:\d+(?:\s*[-,，]\s*\d+)*)】)",
            "",
            segment.text,
        ).strip()
    allowed_ids = {item.chunk.chunk_id for item in evidence}
    if answer.refusal:
        return GroundedAnswer(
            refusal=True,
            refusal_reason=answer.refusal_reason or "当前知识库没有足够依据",
        )
    if not answer.segments:
        return _refusal("生成结果为空")
    for segment in answer.segments:
        if not segment.citation_ids or not set(segment.citation_ids).issubset(allowed_ids):
            return _refusal("回答未通过引用完整性校验")
    if not _all_numbers_grounded(answer, evidence):
        return _refusal("回答中的数字或日期未被所引证据支持")

    if strict_verification:
        verified = await _verify_answer(answer, evidence, provider)
        if not verified and not _role_answer_lexically_grounded(answer, evidence):
            return _refusal("回答未通过证据一致性校验")
    return answer


async def _verify_answer(
    answer: GroundedAnswer,
    evidence: list[RetrievedChunk],
    provider: ChatProvider,
) -> bool:
    lookup = {item.chunk.chunk_id: item.chunk.text for item in evidence}
    checks = []
    for index, segment in enumerate(answer.segments):
        cited = "\n".join(f"[{cid}] {lookup[cid]}" for cid in segment.citation_ids)
        checks.append(f"段落{index + 1}：{segment.text}\n引用：\n{cited}")
    result = await provider.complete_json(
        """你是严格的事实核验器。判断每个段落中的可核查内容是否由其引用证据支持。
允许忠实改写、同义表达、对直接列举内容的概括，以及将角色设定改为第一人称；不要仅因措辞不完全相同判为不支持。
只有当段落增加了证据未提供的具体事实、因果、数字，或与证据矛盾时，才判为不支持。
不得使用外部知识。只输出 JSON。""",
        "\n\n".join(checks),
        {
            "type": "object",
            "properties": {
                "supported": {"type": "boolean"},
                "unsupported_segments": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["supported", "unsupported_segments"],
        },
    )
    return bool(result.get("supported")) and not result.get("unsupported_segments")


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
        raise


def _refusal(reason: str) -> GroundedAnswer:
    return GroundedAnswer(refusal=True, refusal_reason=reason)


def _all_numbers_grounded(
    answer: GroundedAnswer,
    evidence: list[RetrievedChunk],
) -> bool:
    lookup = {item.chunk.chunk_id: item.chunk.text for item in evidence}
    for segment in answer.segments:
        cited_text = "\n".join(lookup[cid] for cid in segment.citation_ids)
        claims = set(re.findall(r"(?<![A-Za-z])\d+(?:[.:-]\d+)*(?![A-Za-z])", segment.text))
        evidence_numbers = set(
            re.findall(r"(?<![A-Za-z])\d+(?:[.:-]\d+)*(?![A-Za-z])", cited_text)
        )
        if not claims.issubset(evidence_numbers):
            return False
    return True


def _role_answer_lexically_grounded(
    answer: GroundedAnswer,
    evidence: list[RetrievedChunk],
) -> bool:
    """Resolve verifier false negatives only for the team's creative-setting records.

    Historical claims never use this fallback. Every role segment must cite only
    role records and retain strong phrase-level overlap with its cited text.
    """
    lookup = {item.chunk.chunk_id: item.chunk.text for item in evidence}
    for segment in answer.segments:
        if not segment.citation_ids or any(
            not cid.startswith(("role-design-", "role-profile-"))
            for cid in segment.citation_ids
        ):
            return False
        cited_text = "\n".join(lookup.get(cid, "") for cid in segment.citation_ids)
        if token_overlap(segment.text, cited_text) < 0.62:
            return False
    return True
