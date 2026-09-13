from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.app.config import get_settings
from backend.app.embeddings import create_embedding_provider
from backend.app.retrieval import Retriever
from backend.app.store import KnowledgeStore


async def main() -> None:
    settings = get_settings()
    store = KnowledgeStore(settings.rag_index_path)
    if not store.exists:
        raise SystemExit("索引不存在，请先运行 python -m backend.scripts.build_index")
    provider = create_embedding_provider(settings)
    retriever = Retriever(store, provider, settings)
    cases = json.loads(Path("knowledge/eval/questions.json").read_text(encoding="utf-8"))["questions"]

    supported_total = 0
    supported_hit = 0
    refusal_total = 0
    refusal_hit = 0
    details = []
    for index, case in enumerate(cases, 1):
        if provider.name == "dashscope" and case["category"] == "supported":
            # The competition workspace has a conservative burst quota.  Keep
            # the fixed evaluation reproducible without weakening runtime's
            # fail-closed behaviour when vector retrieval is unavailable.
            await asyncio.sleep(0.4)
        try:
            results, sufficient, reason = await retriever.retrieve(case["question"])
        except RuntimeError:
            print(f"[{index:02d}/{len(cases)}] ERROR {case['id']}", flush=True)
            raise
        source_ids = [item.chunk.source_id for item in results]
        passed = False
        if case["category"] == "supported":
            supported_total += 1
            expected = set(case["expected_sources"])
            passed = sufficient and bool(expected & set(source_ids))
            supported_hit += int(passed)
        else:
            refusal_total += 1
            passed = not sufficient
            refusal_hit += int(passed)
        details.append(
            {
                "id": case["id"],
                "passed": passed,
                "sufficient": sufficient,
                "sources": source_ids,
                "reason": reason,
            }
        )
        print(
            f"[{index:02d}/{len(cases)}] {'OK' if passed else 'FAIL'} {case['id']}",
            flush=True,
        )

    report = {
        "evaluated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "embedding_provider": provider.name,
        "embedding_model": provider.model,
        "index_metadata": store.index_metadata(),
        "supported_recall_at_6": supported_hit / max(supported_total, 1),
        "refusal_accuracy": refusal_hit / max(refusal_total, 1),
        "supported": {"passed": supported_hit, "total": supported_total},
        "refusal": {"passed": refusal_hit, "total": refusal_total},
        "details": details,
    }
    output = Path(".data/retrieval-evaluation.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"details", "index_metadata"}}, ensure_ascii=False, indent=2))
    print(f"完整报告：{output}")
    if report["supported_recall_at_6"] < 0.9 or report["refusal_accuracy"] < 1.0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
