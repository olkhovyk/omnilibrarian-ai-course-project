from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RetrievalEvalCase:
    id: str
    query: str
    game_id: str
    expected_titles: list[str]
    category: str | None = None
    expected_terms: list[str] | None = None
    expected_source_ids: list[str] | None = None


def load_retrieval_golden(path: str | Path) -> list[RetrievalEvalCase]:
    cases: list[RetrievalEvalCase] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            cases.append(
                RetrievalEvalCase(
                    id=str(payload["id"]),
                    query=str(payload["query"]),
                    game_id=str(payload.get("game_id") or "bg3"),
                    expected_titles=[str(title) for title in payload["expected_titles"]],
                    category=payload.get("category"),
                    expected_terms=[str(term) for term in payload.get("expected_terms", [])],
                    expected_source_ids=[str(source_id) for source_id in payload.get("expected_source_ids", [])],
                )
            )
    return cases


def evaluate_retrieval_results(cases: Iterable[dict]) -> dict[str, float]:
    rows = list(cases)
    total = len(rows)
    if total == 0:
        return {
            "total": 0,
            "hit_at_1": 0.0,
            "hit_at_3": 0.0,
            "hit_at_5": 0.0,
            "mrr": 0.0,
            "coverage_at_5": 0.0,
            "term_coverage_at_5": 0.0,
            "tenant_isolation": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
        }

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_rank_sum = 0.0
    coverage_sum = 0.0
    term_coverage_sum = 0.0
    tenant_isolation_hits = 0
    source_expectation_total = 0
    source_hits_at_5 = 0
    latencies = []

    for case in rows:
        expected_titles = _normalize_titles(case.get("expected_titles", []))
        result_titles = _normalize_titles(result.get("title") for result in case.get("results", []))

        rank = _first_expected_rank(expected_titles, result_titles)
        if rank == 1:
            hits_at_1 += 1
        if rank is not None and rank <= 3:
            hits_at_3 += 1
        if rank is not None and rank <= 5:
            hits_at_5 += 1
            reciprocal_rank_sum += 1 / rank

        coverage_sum += _expected_title_coverage(expected_titles, result_titles[:5])
        term_coverage_sum += _expected_term_coverage(case.get("expected_terms", []), case.get("results", [])[:5])
        if _case_tenant_isolated(case.get("game_id"), case.get("results", [])):
            tenant_isolation_hits += 1
        expected_source_ids = case.get("expected_source_ids") or []
        if expected_source_ids:
            source_expectation_total += 1
            if _case_source_hit_at_k(expected_source_ids, case.get("results", []), k=5):
                source_hits_at_5 += 1
        if case.get("latency_ms") is not None:
            latencies.append(float(case["latency_ms"]))

    return {
        "total": total,
        "hit_at_1": hits_at_1 / total,
        "hit_at_3": hits_at_3 / total,
        "hit_at_5": hits_at_5 / total,
        "mrr": reciprocal_rank_sum / total,
        "coverage_at_5": coverage_sum / total,
        "term_coverage_at_5": term_coverage_sum / total,
        "tenant_isolation": tenant_isolation_hits / total,
        "source_hit_at_5": source_hits_at_5 / source_expectation_total if source_expectation_total else 0.0,
        "source_expectation_total": float(source_expectation_total),
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "p95_latency_ms": _percentile(latencies, 0.95),
        **_category_metrics(rows),
    }


def run_retrieval_eval(*, retriever, cases: Iterable[RetrievalEvalCase], limit: int = 5) -> tuple[list[dict], dict[str, float]]:
    evaluated_cases: list[dict] = []
    for case in cases:
        started = time.perf_counter()
        results = retriever.search(case.query, game_id=case.game_id, limit=limit)
        latency_ms = int((time.perf_counter() - started) * 1000)
        evaluated_cases.append(
            {
                "id": case.id,
                "query": case.query,
                "game_id": case.game_id,
                "category": case.category,
                "expected_titles": case.expected_titles,
                "expected_source_ids": case.expected_source_ids or [],
                "expected_terms": case.expected_terms or [],
                "results": results,
                "top_titles": [result.get("title") for result in results],
                "retrieval_query": results[0].get("retrieval_query") if results else case.query,
                "rewrite_reasons": results[0].get("rewrite_reasons") if results else [],
                "latency_ms": latency_ms,
                "hit_at_1": _case_hit_at_k(case.expected_titles, results, k=1),
                "hit_at_5": _case_hit_at_k(case.expected_titles, results, k=5),
                "source_hit_at_5": _case_source_hit_at_k(case.expected_source_ids or [], results, k=5),
                "term_coverage_at_5": _expected_term_coverage(case.expected_terms or [], results[:5]),
                "tenant_isolated": _case_tenant_isolated(case.game_id, results),
            }
        )

    return evaluated_cases, evaluate_retrieval_results(evaluated_cases)


def write_eval_report(path: str | Path, *, cases: list[dict], metrics: dict[str, float]) -> None:
    report = {
        "metrics": metrics,
        "cases": [
            {
                "id": case["id"],
                "query": case["query"],
                "game_id": case["game_id"],
                "category": case.get("category"),
                "expected_titles": case["expected_titles"],
                "expected_source_ids": case.get("expected_source_ids") or [],
                "top_titles": case["top_titles"],
                "retrieval_query": case.get("retrieval_query"),
                "rewrite_reasons": case.get("rewrite_reasons") or [],
                "latency_ms": case.get("latency_ms"),
                "hit_at_1": case.get("hit_at_1"),
                "hit_at_5": case.get("hit_at_5"),
                "source_hit_at_5": case.get("source_hit_at_5"),
                "term_coverage_at_5": case.get("term_coverage_at_5"),
                "tenant_isolated": case.get("tenant_isolated"),
                "results": [
                    {
                        "title": result.get("title"),
                        "game_id": result.get("game_id"),
                        "source_id": result.get("source_id"),
                        "section": result.get("section"),
                        "content_type": result.get("content_type"),
                        "score": result.get("score"),
                        "rerank_score": result.get("rerank_score"),
                        "source_policy_reasons": result.get("source_policy_reasons") or [],
                        "source_url": result.get("source_url"),
                    }
                    for result in case["results"]
                ],
            }
            for case in cases
        ],
    }
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_titles(titles: Iterable[object]) -> list[str]:
    return [str(title).casefold() for title in titles if title]


def _first_expected_rank(expected_titles: list[str], result_titles: list[str]) -> int | None:
    for index, title in enumerate(result_titles, start=1):
        if title in expected_titles:
            return index
    return None


def _expected_title_coverage(expected_titles: list[str], result_titles: list[str]) -> float:
    if not expected_titles:
        return 0.0
    matched = len(set(expected_titles).intersection(result_titles))
    return matched / len(set(expected_titles))


def _case_hit_at_k(expected_titles: list[str], results: list[dict], *, k: int) -> bool:
    expected = set(_normalize_titles(expected_titles))
    result_titles = set(_normalize_titles(result.get("title") for result in results[:k]))
    return bool(expected.intersection(result_titles))


def _expected_term_coverage(expected_terms: Iterable[object], results: list[dict]) -> float:
    terms = [str(term).casefold() for term in expected_terms if term]
    if not terms:
        return 0.0
    haystack = "\n".join(
        " ".join(
            [
                str(result.get("title") or ""),
                str(result.get("section") or ""),
                str(result.get("text") or ""),
            ]
        )
        for result in results
    ).casefold()
    matched = sum(1 for term in terms if term in haystack)
    return matched / len(terms)


def _case_tenant_isolated(game_id: object, results: list[dict]) -> bool:
    if not game_id:
        return True
    for result in results:
        result_game_id = result.get("game_id")
        if result_game_id is not None and result_game_id != game_id:
            return False
    return True


def _case_source_hit_at_k(expected_source_ids: Iterable[object], results: list[dict], *, k: int) -> bool:
    expected = {str(source_id).casefold() for source_id in expected_source_ids if source_id}
    if not expected:
        return False
    found = {str(result.get("source_id") or "").casefold() for result in results[:k]}
    return bool(expected.intersection(found))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _category_metrics(rows: list[dict]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    categories = sorted({str(row.get("category")) for row in rows if row.get("category")})
    for category in categories:
        category_rows = [row for row in rows if row.get("category") == category]
        if not category_rows:
            continue
        hit_at_1 = sum(
            1
            for row in category_rows
            if _case_hit_at_k(row.get("expected_titles", []), row.get("results", []), k=1)
        )
        hit_at_5 = sum(
            1
            for row in category_rows
            if _case_hit_at_k(row.get("expected_titles", []), row.get("results", []), k=5)
        )
        metrics[f"category.{category}.total"] = float(len(category_rows))
        metrics[f"category.{category}.hit_at_1"] = hit_at_1 / len(category_rows)
        metrics[f"category.{category}.hit_at_5"] = hit_at_5 / len(category_rows)
    return metrics
