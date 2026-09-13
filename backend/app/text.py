from __future__ import annotations

import re


_CJK = re.compile(r"[\u3400-\u9fff]")
_LATIN_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*")


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def lexical_tokens(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    cjk = "".join(_CJK.findall(normalized))
    tokens: list[str] = []
    if len(cjk) == 1:
        tokens.append(cjk)
    else:
        tokens.extend(cjk[index : index + 2] for index in range(len(cjk) - 1))
    tokens.extend(match.group(0).lower() for match in _LATIN_WORD.finditer(normalized))
    return list(dict.fromkeys(token for token in tokens if token.strip()))


def lexicalize(text: str) -> str:
    return " ".join(lexical_tokens(text))


def chunk_text(text: str, target: int = 400, overlap: int = 80) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    paragraphs = [item.strip() for item in re.split(r"\n+", text) if item.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > target * 2:
            sentences = [s for s in re.split(r"(?<=[。！？；])", paragraph) if s]
        else:
            sentences = [paragraph]
        for sentence in sentences:
            if current and len(current) + len(sentence) > target:
                chunks.append(current.strip())
                tail = current[-overlap:] if overlap else ""
                current = f"{tail}{sentence}"
            else:
                current = f"{current}\n{sentence}" if current else sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks


def token_overlap(query: str, document: str) -> float:
    query_tokens = set(lexical_tokens(query))
    if not query_tokens:
        return 0.0
    document_tokens = set(lexical_tokens(document))
    return len(query_tokens & document_tokens) / len(query_tokens)
