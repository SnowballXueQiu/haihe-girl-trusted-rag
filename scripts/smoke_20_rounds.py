from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from backend.app.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if event and isinstance(data, dict):
            events.append((event, data))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="连续20轮可信问答接口烟雾测试")
    parser.add_argument(
        "--base-url",
        default=f"http://127.0.0.1:{Settings().app_port}",
    )
    parser.add_argument("--supported", type=int, default=10)
    parser.add_argument("--refused", type=int, default=10)
    parser.add_argument(
        "--verify-speech",
        action="store_true",
        help="对部分已校验回答实际请求语音，而非只检查令牌",
    )
    parser.add_argument("--speech-limit", type=int, default=2)
    args = parser.parse_args()

    payload = json.loads((ROOT / "knowledge/eval/questions.json").read_text(encoding="utf-8"))
    supported = [item for item in payload["questions"] if item["category"] == "supported"][: args.supported]
    refused = [item for item in payload["questions"] if item["category"] != "supported"][: args.refused]
    cases = [item for pair in zip(supported, refused, strict=False) for item in pair]
    cases.extend(supported[len(refused) :])
    cases.extend(refused[len(supported) :])

    health = httpx.get(f"{args.base_url}/api/health", timeout=10).json()
    results: list[dict] = []
    speech_checks = 0
    with httpx.Client(timeout=600.0) as client:
        for index, case in enumerate(cases, 1):
            started = time.perf_counter()
            response = client.post(
                f"{args.base_url}/api/query",
                json={"question": case["question"], "session_id": "smoke-20"},
            )
            elapsed = round(time.perf_counter() - started, 3)
            events = parse_sse(response.text)
            final = next((data for event, data in reversed(events) if event == "final"), None)
            errors = [data for event, data in events if event == "error"]
            expected_refusal = case["category"] != "supported"
            passed = bool(
                response.status_code == 200
                and final
                and not errors
                and bool(final.get("refused")) == expected_refusal
                and (
                    not expected_refusal
                    and bool(final.get("citations"))
                    and bool(final.get("speech_token"))
                    or expected_refusal
                    and not final.get("citations")
                    and not final.get("speech_token")
                )
            )
            speech_status = None
            speech_bytes = 0
            if (
                passed
                and args.verify_speech
                and not expected_refusal
                and speech_checks < args.speech_limit
            ):
                speech_response = client.post(
                    f"{args.base_url}/api/speech",
                    json={"speech_token": final["speech_token"]},
                )
                speech_checks += 1
                speech_status = speech_response.status_code
                speech_bytes = len(speech_response.content)
                passed = bool(
                    speech_response.status_code == 200
                    and speech_response.headers.get("content-type", "").startswith("audio/")
                    and speech_bytes > 44
                )
            results.append({
                "round": index,
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "elapsed_seconds": elapsed,
                "passed": passed,
                "refused": final.get("refused") if final else None,
                "citation_count": len(final.get("citations", [])) if final else 0,
                "speech_status": speech_status,
                "speech_bytes": speech_bytes,
                "error": errors[0].get("message") if errors else None,
            })
            print(f"[{index:02d}/{len(cases)}] {'OK' if passed else 'FAIL'} {case['id']} {elapsed:.1f}s")

    report = {
        "evaluated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "health": health,
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "speech_checks": speech_checks,
        "results": results,
    }
    output = ROOT / ".data/end-to-end-smoke.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告：{output.relative_to(ROOT)}，{report['passed']}/{report['total']} 通过")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
