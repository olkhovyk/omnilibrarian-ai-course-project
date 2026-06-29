from __future__ import annotations

import re


HINT_TERMS = {
    "hint",
    "hints",
    "stuck",
    "spoiler",
    "spoilers",
    "help",
    "підказ",
    "підказка",
    "підкажи",
    "застряг",
    "спойлер",
}


class SourceRetrievalPolicy:
    def apply(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return []

        if _is_hint_query(query):
            return [_with_source_policy_score(result, reddit_hint_boost=True) for result in results]
        return [_with_source_policy_score(result, wiki_fact_boost=True) for result in results]

    def finalize(self, query: str, results: list[dict]) -> list[dict]:
        if not _is_hint_query(query):
            return results
        return sorted(results, key=_hint_sort_key, reverse=True)


def _with_source_policy_score(
    result: dict,
    *,
    wiki_fact_boost: bool = False,
    reddit_hint_boost: bool = False,
) -> dict:
    adjusted = dict(result)
    score = float(adjusted.get("score") or 0.0)
    reasons = list(adjusted.get("source_policy_reasons") or [])
    source_id = str(adjusted.get("source_id") or "")

    if wiki_fact_boost and source_id.endswith("_wiki"):
        score += 0.35
        reasons.append("source_policy:prefer_wiki_facts")
    if wiki_fact_boost and source_id.endswith("_reddit"):
        score -= 0.15
        reasons.append("source_policy:deprioritize_reddit_for_facts")
    if reddit_hint_boost and source_id.endswith("_reddit"):
        score += 0.45
        reasons.append("source_policy:prefer_reddit_hints")

    adjusted["score"] = score
    adjusted["source_policy_reasons"] = reasons
    return adjusted


def _is_hint_query(query: str) -> bool:
    tokens = set(re.findall(r"[\w]+", query.casefold(), flags=re.UNICODE))
    return bool(tokens & HINT_TERMS)


def _hint_sort_key(result: dict) -> tuple[int, float]:
    source_id = str(result.get("source_id") or "")
    return (
        1 if source_id.endswith("_reddit") else 0,
        float(result.get("rerank_score") or result.get("score") or 0.0),
    )
