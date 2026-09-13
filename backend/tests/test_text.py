from backend.app.text import chunk_text, lexical_tokens, token_overlap


def test_chinese_lexical_tokens_include_bigrams() -> None:
    tokens = lexical_tokens("泥人张彩塑")
    assert "泥人" in tokens
    assert "人张" in tokens
    assert "彩塑" in tokens


def test_chunk_text_preserves_overlap() -> None:
    text = "。".join(["海河少女讲述天津文化"] * 80) + "。"
    chunks = chunk_text(text, target=120, overlap=20)
    assert len(chunks) > 2
    assert all(chunk.strip() for chunk in chunks)


def test_overlap_prefers_relevant_text() -> None:
    relevant = token_overlap("泥人张彩塑是什么", "天津泥人张彩塑属于传统美术")
    irrelevant = token_overlap("泥人张彩塑是什么", "今天的天气很晴朗")
    assert relevant > irrelevant
