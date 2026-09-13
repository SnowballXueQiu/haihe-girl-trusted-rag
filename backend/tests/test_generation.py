import json

import httpx

from backend.app import generation
from backend.app.config import Settings
from backend.app.generation import (
    ChatProvider,
    DashScopeChatProvider,
    _role_answer_lexically_grounded,
    generate_grounded_answer,
)
from backend.app.models import AnswerSegment, ChunkRecord, GroundedAnswer, RetrievedChunk


class FakeProvider(ChatProvider):
    name = "fake"
    model = "fake-v1"

    def __init__(
        self,
        invalid_citation: bool = False,
        verification: bool = True,
        invented_number: bool = False,
        redundant_marker: bool = False,
        numeric_markers: bool = False,
    ) -> None:
        self.calls = 0
        self.invalid_citation = invalid_citation
        self.verification = verification
        self.invented_number = invented_number
        self.redundant_marker = redundant_marker
        self.numeric_markers = numeric_markers

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "segments": [
                    {
                        "text": (
                            "泥人张彩塑始于1860年。"
                            if self.invented_number
                            else "泥人张彩塑属于传统美术类国家级非物质文化遗产。"
                            + ("[证据块 official-0001]" if self.redundant_marker else "")
                            + ("[1]" if self.numeric_markers else "")
                        ),
                        "citation_ids": ["wrong-id" if self.invalid_citation else "official-0001"],
                    }
                ],
                "refusal": False,
                "refusal_reason": None,
            }
        return {"supported": self.verification, "unsupported_segments": [] if self.verification else [1]}


def evidence() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk=ChunkRecord(
                chunk_id="official-0001",
                source_id="official",
                title="官方资料",
                publisher="官方",
                topic="泥人张",
                text="泥塑（天津泥人张）类别为传统美术。",
                search_text="泥人 张彩 彩塑",
                page=None,
                section=None,
                url="https://example.com",
            )
        )
    ]


async def test_grounded_answer_passes_two_stage_validation() -> None:
    result = await generate_grounded_answer("泥人张属于什么类别？", evidence(), FakeProvider(), True)
    assert not result.refusal
    assert "传统美术" in result.text


async def test_unknown_citation_forces_refusal() -> None:
    result = await generate_grounded_answer(
        "泥人张属于什么类别？", evidence(), FakeProvider(invalid_citation=True), True
    )
    assert result.refusal


async def test_failed_semantic_verification_forces_refusal() -> None:
    result = await generate_grounded_answer(
        "泥人张属于什么类别？", evidence(), FakeProvider(verification=False), True
    )
    assert result.refusal


async def test_number_not_present_in_citation_forces_refusal() -> None:
    result = await generate_grounded_answer(
        "泥人张何时创立？", evidence(), FakeProvider(invented_number=True), True
    )
    assert result.refusal
    assert "数字" in (result.refusal_reason or "")


async def test_redundant_inline_citation_marker_is_removed() -> None:
    result = await generate_grounded_answer(
        "泥人张属于什么类别？", evidence(), FakeProvider(redundant_marker=True), False
    )
    assert not result.refusal
    assert result.text == "泥人张彩塑属于传统美术类国家级非物质文化遗产。"


async def test_numeric_inline_citation_marker_is_removed_before_number_check() -> None:
    result = await generate_grounded_answer(
        "泥人张属于什么类别？", evidence(), FakeProvider(numeric_markers=True), False
    )
    assert not result.refusal
    assert result.text == "泥人张彩塑属于传统美术类国家级非物质文化遗产。"


def test_role_fallback_requires_role_source_and_strong_overlap() -> None:
    role_evidence = RetrievedChunk(
        chunk=ChunkRecord(
            chunk_id="role-design-0001",
            source_id="role-design",
            title="角色设计",
            publisher="参赛团队原创",
            topic="角色设计",
            text="衣身减少大面积花饰，仅藏海棠与水纹暗纹，远看干净素雅。",
            search_text="",
            page=None,
            section=None,
            url=None,
        )
    )
    grounded = GroundedAnswer(
        segments=[
            AnswerSegment(
                text="衣身减少大面积花饰，只保留海棠与水纹暗纹，远看干净素雅。",
                citation_ids=["role-design-0001"],
            )
        ]
    )
    invented = GroundedAnswer(
        segments=[
            AnswerSegment(
                text="这套衣服是在2026年由著名设计师全手工制作的。",
                citation_ids=["role-design-0001"],
            )
        ]
    )
    assert _role_answer_lexically_grounded(grounded, [role_evidence])
    assert not _role_answer_lexically_grounded(invented, [role_evidence])


async def test_dashscope_chat_receives_workspace_and_schema(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    schema = {
        "type": "object",
        "properties": {"supported": {"type": "boolean"}},
        "required": ["supported"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-dashscope-workspace"] == "ws-test"
        payload = json.loads(request.content)
        assert payload["enable_thinking"] is False
        assert payload["response_format"] == {"type": "json_object"}
        assert "JSON Schema" in payload["messages"][0]["content"]
        assert '"supported"' in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"supported":true}'}}]},
        )

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        generation.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        dashscope_workspace_id="ws-test",
        dashscope_compatible_base_url=(
            "https://ws-test.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
        ),
    )
    result = await DashScopeChatProvider(settings).complete_json("只输出 JSON。", "核验", schema)
    assert result == {"supported": True}
