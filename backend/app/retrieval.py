from __future__ import annotations

from .config import Settings
from .embeddings import EmbeddingProvider
from .models import Citation, RetrievedChunk
from .store import KnowledgeStore


PROMPT_INJECTION_MARKERS = (
    "忽略以上",
    "忽略之前",
    "系统提示词",
    "开发者消息",
    "绕过限制",
    "不要引用",
    "ignore previous",
    "system prompt",
    "自己猜",
    "知识库说错",
)

DOMAIN_TERMS = (
    "海河少女",
    "泥人张",
    "泥塑",
    "彩塑",
    "仕女",
    "风筝魏",
    "风筝",
    "魏元泰",
    "魏国秋",
    "海河",
    "漕运",
    "三岔河口",
    "海棠",
    "五大道",
    "角色",
    "服装",
    "服饰",
    "纹样",
    "衣身",
    "暗纹",
    "发色",
    "头发",
    "裙摆",
    "数字人",
    "虚拟主播",
)

REALTIME_TERMS = (
    "实时",
    "多少钱",
    "票价",
    "当前价格",
    "现在的价格",
    "营业时间",
    "开放时间",
)

ROLE_TERMS = (
    "角色设计",
    "角色定位",
    "角色造型",
    "造型",
    "服装",
    "服饰",
    "衣身",
    "纹样",
    "暗纹",
    "色彩",
    "上衣",
    "裙摆",
    "发色",
    "头发",
    "暗纹",
    "艺术风格",
    "说话风格",
    "性格",
    "使命",
)


class Retriever:
    def __init__(
        self,
        store: KnowledgeStore,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self.store = store
        self.embedding_provider = embedding_provider
        self.settings = settings

    async def retrieve(self, question: str) -> tuple[list[RetrievedChunk], bool, str | None]:
        normalized = question.lower()
        if any(marker in normalized for marker in PROMPT_INJECTION_MARKERS):
            return [], False, "检测到试图绕过知识边界的指令"
        if not any(term.lower() in normalized for term in DOMAIN_TERMS):
            return [], False, "问题不在当前知识库的五个主题范围内"
        if _asks_for_realtime(normalized):
            return [], False, "问题需要实时信息，而运行时不联网搜索"

        lexical = self.store.lexical_search(question, limit=30)
        vector_results: list[RetrievedChunk] = []
        try:
            vector = (await self.embedding_provider.embed([question]))[0]
            vector_results = self.store.vector_search(vector, limit=30)
        except Exception as exc:
            if not self.settings.retrieval_allow_lexical_fallback:
                raise RuntimeError("向量检索服务不可用，已停止回答") from exc
            vector_results = []

        fused: dict[str, RetrievedChunk] = {}
        for path, results in (("lexical", lexical), ("vector", vector_results)):
            for rank, result in enumerate(results, 1):
                chunk_id = result.chunk.chunk_id
                if chunk_id not in fused:
                    fused[chunk_id] = result
                else:
                    existing = fused[chunk_id]
                    existing.retrieval_paths.update(result.retrieval_paths)
                    existing.lexical_overlap = max(existing.lexical_overlap, result.lexical_overlap)
                    if result.vector_score is not None:
                        existing.vector_score = result.vector_score
                fused[chunk_id].rank_score += 1.0 / (60 + rank)

        # Generic design questions such as “采用了怎样的色彩层级” can be
        # semantically close to academic design papers.  When the question itself
        # identifies the character/design intent, prefer the team's primary
        # design records without excluding factual sources from the candidate set.
        role_question = any(term in normalized for term in ROLE_TERMS)
        if role_question:
            for result in fused.values():
                if result.chunk.source_id in {"role-design", "role-profile"}:
                    result.rank_score += 0.05

        ranked = sorted(fused.values(), key=lambda item: item.rank_score, reverse=True)
        if role_question:
            # Creative setting is a separate evidence class from historical
            # fact.  When the user asks about this character's own appearance
            # or personality, do not mix in visually similar academic papers.
            role_evidence = [
                item
                for item in ranked
                if item.chunk.source_id in {"role-design", "role-profile"}
            ]
            if role_evidence:
                ranked = role_evidence
        diverse: list[RetrievedChunk] = []
        per_source: dict[str, int] = {}
        for item in ranked:
            count = per_source.get(item.chunk.source_id, 0)
            if count >= 2:
                continue
            diverse.append(item)
            per_source[item.chunk.source_id] = count + 1
            if len(diverse) >= self.settings.retrieval_top_k:
                break

        if not diverse:
            return [], False, "知识库没有检索到相关证据"
        top = diverse[0]
        sufficient = (
            top.lexical_overlap >= self.settings.retrieval_lexical_threshold
            or (top.vector_score or -1.0) >= self.settings.retrieval_vector_threshold
        )
        reason = None if sufficient else "检索结果与问题的相关度不足"
        return diverse, sufficient, reason


def to_citations(results: list[RetrievedChunk]) -> list[Citation]:
    citations: list[Citation] = []
    for item in results:
        chunk = item.chunk
        url = chunk.url or f"/api/sources/{chunk.source_id}?chunk_id={chunk.chunk_id}"
        if chunk.page and not chunk.url:
            url = f"{url}#page={chunk.page}"
        citations.append(
            Citation(
                source_id=chunk.source_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                publisher=chunk.publisher,
                page=chunk.page,
                excerpt=chunk.text[:220],
                url=url,
            )
        )
    return citations


def _asks_for_realtime(question: str) -> bool:
    if any(term in question for term in REALTIME_TERMS):
        return True
    # `现在` must be anchored; otherwise `出现在哪里` would be a false positive.
    return question.startswith(("现在", "今天", "明天", "昨天", "目前"))
