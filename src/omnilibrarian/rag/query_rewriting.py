from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnilibrarian.entities.registry import EntityRegistry


@dataclass(frozen=True)
class RewrittenQuery:
    original_query: str
    retrieval_query: str
    rewrite_reasons: list[str]

    @property
    def was_rewritten(self) -> bool:
        return self.original_query != self.retrieval_query


PHRASE_REWRITES = {
    "що завдає більше шкоди": "damage",
}

TOKEN_REWRITES = {
    "порівняй": "compare",
    "порівняти": "compare",
    "порівняння": "comparison",
    "мені": "",
    "з": "with",
    "що": "what",
    "завдає": "",
    "більше": "",
    "шкоди": "damage",
    "урон": "damage",
    "дамаг": "damage",
    "молнія": "Lightning Bolt",
    "молнією": "Lightning Bolt",
    "блискавка": "Lightning Bolt",
    "фаєрбол": "Fireball",
    "фаєрболл": "Fireball",
    "сильніше": "stronger",
    "чи": "or",
    "у": "",
}


def rewrite_query(query: str, entity_registry: "EntityRegistry | None" = None) -> RewrittenQuery:
    rewritten = query
    reasons: list[str] = []

    for phrase, replacement in PHRASE_REWRITES.items():
        rewritten, changed = _replace_phrase(rewritten, phrase, replacement)
        if changed:
            reasons.append(f"{phrase}->{replacement}")

    rewritten_tokens: list[str] = []
    for token in _split_preserving_words(rewritten):
        replacement = TOKEN_REWRITES.get(token.casefold())
        if replacement is None:
            rewritten_tokens.append(token)
            continue
        if replacement:
            rewritten_tokens.extend(replacement.split())
        reasons.append(f"{token}->{replacement}")

    rewritten_tokens, fuzzy_reasons = _rewrite_entity_typos(rewritten_tokens, entity_registry)
    reasons.extend(fuzzy_reasons)
    retrieval_query = _clean_query(" ".join(rewritten_tokens))
    original_clean = _clean_query(query)
    if retrieval_query == original_clean:
        reasons = []
    return RewrittenQuery(
        original_query=query,
        retrieval_query=retrieval_query,
        rewrite_reasons=reasons,
    )


def _rewrite_entity_typos(
    tokens: list[str],
    entity_registry: "EntityRegistry | None",
) -> tuple[list[str], list[str]]:
    if entity_registry is None:
        return tokens, []

    rewritten_tokens: list[str] = []
    reasons: list[str] = []
    for token in tokens:
        entity = entity_registry.find_fuzzy(token)
        if entity is None:
            rewritten_tokens.append(token)
            continue
        rewritten_tokens.extend(entity.canonical_name.split())
        if token.casefold() != entity.canonical_name.casefold():
            reasons.append(f"{token}->{entity.canonical_name}:fuzzy")
    return rewritten_tokens, reasons


def _replace_phrase(text: str, phrase: str, replacement: str) -> tuple[str, bool]:
    pattern = re.compile(re.escape(phrase), flags=re.IGNORECASE)
    rewritten, count = pattern.subn(replacement, text)
    return rewritten, count > 0


def _split_preserving_words(text: str) -> list[str]:
    return re.findall(r"[\w]+", text, flags=re.UNICODE)


def _clean_query(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
