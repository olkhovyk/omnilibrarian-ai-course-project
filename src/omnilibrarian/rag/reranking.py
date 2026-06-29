from __future__ import annotations

import re


TITLE_EXACT_BONUS = 0.8
TITLE_TOKEN_BONUS = 0.12
TEXT_TERM_BONUS = 0.04
DEFINITION_LEAD_SECTION_BONUS = 0.12
SECTION_DIVERSITY_THRESHOLD = 0.35
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "by",
    "for",
    "in",
    "is",
    "me",
    "of",
    "or",
    "the",
    "to",
    "with",
    "що",
    "з",
    "і",
    "мені",
}
COMPARATIVE_TERMS = {
    "compare",
    "comparison",
    "versus",
    "vs",
    "difference",
    "better",
    "порівняй",
    "порівняти",
    "порівняння",
    "проти",
    "різниця",
    "краще",
}
DEFINITION_TERMS = {
    "who",
    "what",
    "describe",
    "overview",
    "about",
    "хто",
    "що",
    "опис",
    "розкажи",
}
LEAD_SECTIONS = {
    "lead",
    "overview",
    "description",
    "background",
}


def is_comparative_query(query: str) -> bool:
    tokens = set(_tokens(query))
    return bool(tokens & COMPARATIVE_TERMS)


def rerank_results(query: str, results: list[dict], limit: int) -> list[dict]:
    scored = [_score_result(query, result) for result in results]
    scored.sort(key=_sort_key, reverse=True)
    if is_comparative_query(query):
        scored = _diversify_by_title(scored, limit)
    elif _is_definitional_query(query):
        scored = _diversify_exact_title_sections(scored, limit)
    return scored[:limit]


def _score_result(query: str, result: dict) -> dict:
    query_normalized = _normalize(query)
    query_tokens = _important_tokens(query)
    title = str(result.get("title") or "")
    title_normalized = _normalize(title)
    title_tokens = _important_tokens(title)
    section_normalized = _normalize(str(result.get("section") or ""))
    text_normalized = _normalize(str(result.get("text") or ""))
    score = float(result.get("score") or 0.0)
    reasons: list[str] = []
    has_exact_title = False
    is_lead_definition_section = False

    if title_normalized and title_normalized in query_normalized:
        score += TITLE_EXACT_BONUS
        reasons.append(f"title_exact:{title_normalized}")
        has_exact_title = True

    for token in title_tokens:
        if token in query_tokens and title_normalized not in query_normalized:
            score += TITLE_TOKEN_BONUS
            reasons.append(f"title_token:{token}")

    if has_exact_title and section_normalized in LEAD_SECTIONS and _is_definitional_query(query):
        score += DEFINITION_LEAD_SECTION_BONUS
        reasons.append("section_lead_for_definition")
        is_lead_definition_section = True

    for token in query_tokens:
        if token in text_normalized:
            score += TEXT_TERM_BONUS
            reasons.append(f"text_term:{token}")

    reranked = dict(result)
    reranked["rerank_score"] = score
    reranked["rerank_reasons"] = reasons
    reranked["rerank_exact_title_match"] = has_exact_title
    reranked["rerank_definition_lead_section"] = is_lead_definition_section
    return reranked


def _sort_key(result: dict) -> tuple[int, int, float]:
    return (
        1 if result.get("rerank_exact_title_match") else 0,
        1 if result.get("rerank_definition_lead_section") else 0,
        float(result.get("rerank_score") or 0.0),
    )


def _diversify_by_title(results: list[dict], limit: int) -> list[dict]:
    selected: list[dict] = []
    selected_titles: set[str] = set()
    remaining = list(results)

    while remaining and len(selected) < limit:
        index = _next_diverse_index(remaining, selected_titles)
        result = remaining.pop(index)
        title = _normalize(str(result.get("title") or ""))
        if selected_titles and title not in selected_titles:
            reasons = list(result.get("rerank_reasons") or [])
            reasons.append("comparative_diversity")
            result = {**result, "rerank_reasons": reasons}
        selected.append(result)
        selected_titles.add(title)

    selected.extend(remaining)
    return selected


def _next_diverse_index(results: list[dict], selected_titles: set[str]) -> int:
    if not selected_titles:
        return 0
    best_score = float(results[0].get("rerank_score") or 0.0)
    threshold = best_score - 0.2
    for index, result in enumerate(results):
        title = _normalize(str(result.get("title") or ""))
        score = float(result.get("rerank_score") or 0.0)
        if title not in selected_titles and score >= threshold:
            return index
    return 0


def _diversify_exact_title_sections(results: list[dict], limit: int) -> list[dict]:
    selected: list[dict] = []
    selected_sections: set[tuple[str, str]] = set()
    remaining = list(results)

    while remaining and len(selected) < limit:
        index = _next_diverse_section_index(remaining, selected_sections)
        result = remaining.pop(index)
        title = _normalize(str(result.get("title") or ""))
        section = _normalize(str(result.get("section") or ""))
        section_key = (title, section)
        if selected_sections and section_key not in selected_sections and result.get("rerank_exact_title_match"):
            reasons = list(result.get("rerank_reasons") or [])
            reasons.append("section_diversity")
            result = {**result, "rerank_reasons": reasons}
        selected.append(result)
        selected_sections.add(section_key)

    selected.extend(remaining)
    return selected


def _next_diverse_section_index(results: list[dict], selected_sections: set[tuple[str, str]]) -> int:
    if not selected_sections:
        return 0
    best_score = float(results[0].get("rerank_score") or 0.0)
    threshold = best_score - SECTION_DIVERSITY_THRESHOLD
    for index, result in enumerate(results):
        if not result.get("rerank_exact_title_match"):
            continue
        title = _normalize(str(result.get("title") or ""))
        section = _normalize(str(result.get("section") or ""))
        score = float(result.get("rerank_score") or 0.0)
        if (title, section) not in selected_sections and score >= threshold:
            return index
    return 0


def _is_definitional_query(query: str) -> bool:
    tokens = set(_tokens(query))
    return bool(tokens & DEFINITION_TERMS)


def _important_tokens(text: str) -> set[str]:
    return {token for token in _tokens(text) if token not in STOPWORDS and len(token) > 1}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", _normalize(text), flags=re.UNICODE)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()
