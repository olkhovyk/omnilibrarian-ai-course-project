from __future__ import annotations

from dataclasses import dataclass
import json
import time
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ToolRoutingEvalCase:
    id: str
    query: str
    game_id: str
    expected_tool: str | None
    category: str | None = None


def load_tool_routing_golden(path: str | Path) -> list[ToolRoutingEvalCase]:
    cases: list[ToolRoutingEvalCase] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            cases.append(
                ToolRoutingEvalCase(
                    id=str(payload["id"]),
                    query=str(payload["query"]),
                    game_id=str(payload.get("game_id") or "bg3"),
                    expected_tool=payload.get("expected_tool"),
                    category=payload.get("category"),
                )
            )
    return cases


def run_tool_routing_eval(*, router, cases: Iterable[ToolRoutingEvalCase]) -> tuple[list[dict], dict[str, float]]:
    rows = []
    for case in cases:
        started = time.perf_counter()
        selection = router.select(game_id=case.game_id, query=case.query)
        latency_ms = int((time.perf_counter() - started) * 1000)
        selected_tool = selection.tool if selection is not None else None
        rows.append(
            {
                "id": case.id,
                "query": case.query,
                "game_id": case.game_id,
                "category": case.category,
                "expected_tool": case.expected_tool,
                "selected_tool": selected_tool,
                "arguments": selection.arguments if selection is not None else {},
                "passed": selected_tool == case.expected_tool,
                "latency_ms": latency_ms,
            }
        )
    return rows, evaluate_tool_routing_results(rows)


def evaluate_tool_routing_results(rows: Iterable[dict]) -> dict[str, float]:
    cases = list(rows)
    total = len(cases)
    if total == 0:
        return {"total": 0, "accuracy": 0.0, "avg_latency_ms": 0.0}
    latencies = [float(case.get("latency_ms") or 0) for case in cases]
    passed = sum(1 for case in cases if case.get("passed"))
    return {
        "total": total,
        "accuracy": passed / total,
        "avg_latency_ms": sum(latencies) / len(latencies),
        **_category_metrics(cases),
    }


def write_tool_routing_report(path: str | Path, *, cases: list[dict], metrics: dict[str, float]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"metrics": metrics, "cases": cases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _category_metrics(rows: list[dict]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    categories = sorted({str(row.get("category")) for row in rows if row.get("category")})
    for category in categories:
        category_rows = [row for row in rows if row.get("category") == category]
        metrics[f"category.{category}.total"] = float(len(category_rows))
        metrics[f"category.{category}.accuracy"] = sum(1 for row in category_rows if row.get("passed")) / len(category_rows)
    return metrics
