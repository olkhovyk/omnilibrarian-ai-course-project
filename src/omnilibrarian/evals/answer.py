from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from pathlib import Path
from typing import Iterable


INSUFFICIENT_CONTEXT_MARKERS = (
    "недостатньо контекст",
    "немає інформації",
    "не знайдено",
    "insufficient context",
    "not enough context",
)


@dataclass(frozen=True)
class AnswerEvalCase:
    id: str
    query: str
    game_id: str
    expected_source_titles: list[str]
    expected_answer_terms: list[str | list[str]]
    category: str | None = None
    allow_insufficient_context: bool = False


def load_answer_golden(path: str | Path) -> list[AnswerEvalCase]:
    cases: list[AnswerEvalCase] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            cases.append(
                AnswerEvalCase(
                    id=str(payload["id"]),
                    query=str(payload["query"]),
                    game_id=str(payload.get("game_id") or "bg3"),
                    expected_source_titles=[str(title) for title in payload.get("expected_source_titles", [])],
                    expected_answer_terms=_load_expected_answer_terms(payload.get("expected_answer_terms", [])),
                    category=payload.get("category"),
                    allow_insufficient_context=bool(payload.get("allow_insufficient_context", False)),
                )
            )
    return cases


def run_answer_eval(
    *,
    retriever,
    answer_generator,
    cases: Iterable[AnswerEvalCase],
    limit: int = 5,
) -> tuple[list[dict], dict[str, float]]:
    rows: list[dict] = []
    for case in cases:
        started = time.perf_counter()
        chunks = retriever.search(case.query, game_id=case.game_id, limit=limit)
        answer_started = time.perf_counter()
        answer = answer_generator.generate(question=case.query, game_id=case.game_id, chunks=chunks)
        total_latency_ms = int((time.perf_counter() - started) * 1000)
        answer_latency_ms = int((time.perf_counter() - answer_started) * 1000)
        rows.append(
            {
                "id": case.id,
                "query": case.query,
                "game_id": case.game_id,
                "category": case.category,
                "expected_source_titles": case.expected_source_titles,
                "expected_answer_terms": case.expected_answer_terms,
                "allow_insufficient_context": case.allow_insufficient_context,
                "answer": answer.answer,
                "sources": answer.sources,
                "cache_status": answer.cache_status,
                "retrieved_titles": [chunk.get("title") for chunk in chunks],
                "retrieval_query": chunks[0].get("retrieval_query") if chunks else case.query,
                "rewrite_reasons": chunks[0].get("rewrite_reasons") if chunks else [],
                "source_hit": _source_hit(case.expected_source_titles, answer.sources),
                "citation_present": _citation_present(answer.answer),
                "answer_term_coverage": _answer_term_coverage(case.expected_answer_terms, answer.answer),
                "insufficient_context": _has_insufficient_context(answer.answer),
                "latency_ms": total_latency_ms,
                "answer_latency_ms": answer_latency_ms,
            }
        )
    return rows, evaluate_answer_results(rows)


def evaluate_answer_results(rows: Iterable[dict]) -> dict[str, float]:
    cases = list(rows)
    total = len(cases)
    if total == 0:
        return {
            "total": 0,
            "source_presence": 0.0,
            "source_hit": 0.0,
            "citation_presence": 0.0,
            "answer_term_coverage": 0.0,
            "grounded_answer_rate": 0.0,
            "no_unexpected_insufficient_context": 0.0,
            "avg_latency_ms": 0.0,
            "avg_answer_latency_ms": 0.0,
        }

    source_presence = sum(1 for row in cases if row.get("sources"))
    source_hit = sum(1 for row in cases if row.get("source_hit"))
    citation_presence = sum(1 for row in cases if row.get("citation_present"))
    no_unexpected_insufficient = sum(
        1
        for row in cases
        if row.get("allow_insufficient_context") or not row.get("insufficient_context")
    )
    grounded = sum(1 for row in cases if _row_grounded(row))
    latencies = [float(row["latency_ms"]) for row in cases if row.get("latency_ms") is not None]
    answer_latencies = [
        float(row["answer_latency_ms"]) for row in cases if row.get("answer_latency_ms") is not None
    ]

    return {
        "total": total,
        "source_presence": source_presence / total,
        "source_hit": source_hit / total,
        "citation_presence": citation_presence / total,
        "answer_term_coverage": sum(float(row.get("answer_term_coverage") or 0.0) for row in cases) / total,
        "grounded_answer_rate": grounded / total,
        "no_unexpected_insufficient_context": no_unexpected_insufficient / total,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "avg_answer_latency_ms": sum(answer_latencies) / len(answer_latencies) if answer_latencies else 0.0,
        **_category_metrics(cases),
    }


def write_answer_eval_report(path: str | Path, *, cases: list[dict], metrics: dict[str, float]) -> None:
    report = {
        "metrics": metrics,
        "cases": [
            {
                "id": case["id"],
                "query": case["query"],
                "game_id": case["game_id"],
                "category": case.get("category"),
                "expected_source_titles": case.get("expected_source_titles", []),
                "expected_answer_terms": case.get("expected_answer_terms", []),
                "retrieved_titles": case.get("retrieved_titles", []),
                "retrieval_query": case.get("retrieval_query"),
                "rewrite_reasons": case.get("rewrite_reasons") or [],
                "answer": case.get("answer"),
                "sources": [
                    {
                        "id": source.get("id"),
                        "title": source.get("title"),
                        "section": source.get("section"),
                        "url": source.get("url"),
                    }
                    for source in case.get("sources", [])
                ],
                "cache_status": case.get("cache_status"),
                "source_hit": case.get("source_hit"),
                "citation_present": case.get("citation_present"),
                "answer_term_coverage": case.get("answer_term_coverage"),
                "insufficient_context": case.get("insufficient_context"),
                "latency_ms": case.get("latency_ms"),
                "answer_latency_ms": case.get("answer_latency_ms"),
            }
            for case in cases
        ],
    }
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_hit(expected_titles: list[str], sources: list[dict]) -> bool:
    if not expected_titles:
        return bool(sources)
    expected = {title.casefold() for title in expected_titles}
    source_titles = {str(source.get("title") or "").casefold() for source in sources}
    return bool(expected.intersection(source_titles))


def _citation_present(answer: str) -> bool:
    return bool(re.search(r"\[\d+\]", answer))


def _answer_term_coverage(expected_terms: list[str | list[str]], answer: str) -> float:
    if not expected_terms:
        return 1.0
    lowered = answer.casefold()
    matched = sum(1 for term in expected_terms if _expected_term_matches(term, lowered))
    return matched / len(expected_terms)


def _load_expected_answer_terms(raw_terms: list[object]) -> list[str | list[str]]:
    terms: list[str | list[str]] = []
    for term in raw_terms:
        if isinstance(term, list):
            terms.append([str(option) for option in term])
        else:
            terms.append(str(term))
    return terms


def _expected_term_matches(term: str | list[str], lowered_answer: str) -> bool:
    if isinstance(term, list):
        return any(option.casefold() in lowered_answer for option in term)
    return term.casefold() in lowered_answer


def _has_insufficient_context(answer: str) -> bool:
    lowered = answer.casefold()
    return any(marker in lowered for marker in INSUFFICIENT_CONTEXT_MARKERS)


def _row_grounded(row: dict) -> bool:
    if not row.get("sources"):
        return False
    if not row.get("citation_present"):
        return False
    if not row.get("source_hit"):
        return False
    if float(row.get("answer_term_coverage") or 0.0) < 1.0:
        return False
    if row.get("insufficient_context") and not row.get("allow_insufficient_context"):
        return False
    return True


def _category_metrics(rows: list[dict]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    categories = sorted({str(row.get("category")) for row in rows if row.get("category")})
    for category in categories:
        category_rows = [row for row in rows if row.get("category") == category]
        if not category_rows:
            continue
        metrics[f"category.{category}.total"] = float(len(category_rows))
        metrics[f"category.{category}.grounded_answer_rate"] = sum(
            1 for row in category_rows if _row_grounded(row)
        ) / len(category_rows)
        metrics[f"category.{category}.source_hit"] = sum(
            1 for row in category_rows if row.get("source_hit")
        ) / len(category_rows)
    return metrics
