from __future__ import annotations

from omnilibrarian.entities.extract import normalize_entity_name
from omnilibrarian.entities.models import Entity


COMMON_NON_ENTITY_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "blue",
    "by",
    "do",
    "does",
    "for",
    "guidance",
    "how",
    "in",
    "is",
    "look",
    "me",
    "of",
    "or",
    "prince",
    "progression",
    "puzzle",
    "puzzles",
    "room",
    "rooms",
    "should",
    "the",
    "to",
    "what",
    "who",
    "with",
    "work",
    "works",
    "damage",
    "compare",
    "comparison",
    "better",
    "stronger",
    "spell",
    "item",
    "class",
}


class EntityRegistry:
    def __init__(self, entities: list[Entity], min_score: int = 88) -> None:
        self.entities = entities
        self.min_score = min_score
        self._choices: dict[str, Entity] = {}
        for entity in entities:
            self._choices[entity.normalized_name] = entity
            for alias in entity.aliases:
                self._choices[normalize_entity_name(alias)] = entity

    def find_fuzzy(self, value: str) -> Entity | None:
        normalized = normalize_entity_name(value)
        if not normalized or normalized in COMMON_NON_ENTITY_TERMS:
            return None
        if normalized in self._choices:
            return self._choices[normalized]
        if len(normalized) < 4:
            return None

        try:
            from rapidfuzz import fuzz, process
        except ImportError as exc:
            raise RuntimeError(
                "rapidfuzz is required for entity fuzzy matching. "
                "Install it with: python -m pip install rapidfuzz"
            ) from exc

        match = process.extractOne(
            normalized,
            list(self._choices.keys()),
            scorer=fuzz.WRatio,
            score_cutoff=self.min_score,
        )
        if match is None:
            return None
        matched_name, _score, _index = match
        return self._choices[matched_name]
