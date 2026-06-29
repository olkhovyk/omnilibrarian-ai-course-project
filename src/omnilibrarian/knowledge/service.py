from __future__ import annotations

from omnilibrarian.entities.extract import normalize_entity_name
from omnilibrarian.entities.models import Entity
from omnilibrarian.entities.registry import EntityRegistry


class KnowledgeService:
    def __init__(self, *, retriever, entity_registry: EntityRegistry | None = None) -> None:
        self.retriever = retriever
        self.entity_registry = entity_registry

    def search(self, *, game_id: str, query: str, limit: int = 5) -> list[dict]:
        return self.retriever.search(query, game_id=game_id, limit=limit)

    def get_entity(self, *, game_id: str, name: str) -> dict | None:
        entity = self._find_entity(game_id=game_id, name=name)
        if entity is None:
            return None
        return entity.to_dict()

    def list_entities(self, *, game_id: str, content_type: str | None = None, limit: int | None = None) -> list[dict]:
        if self.entity_registry is None:
            return []

        entities = []
        for entity in self.entity_registry.entities:
            if entity.game_id != game_id:
                continue
            if content_type is not None and entity.content_type != content_type:
                continue
            entities.append(entity)

        entities.sort(key=lambda entity: entity.canonical_name.casefold())
        if limit is not None:
            entities = entities[:limit]
        return [entity.to_dict() for entity in entities]

    def find_entities(self, *, game_id: str, text: str, content_type: str | None = None) -> list[dict]:
        if self.entity_registry is None:
            return []

        normalized_text = normalize_entity_name(text)
        matches: list[tuple[int, Entity]] = []
        seen: set[str] = set()
        for entity in self.entity_registry.entities:
            if entity.game_id != game_id:
                continue
            if content_type is not None and entity.content_type != content_type:
                continue
            names = [entity.normalized_name, normalize_entity_name(entity.canonical_name)]
            names.extend(normalize_entity_name(alias) for alias in entity.aliases)
            positions = [normalized_text.find(name) for name in names if name and name in normalized_text]
            if not positions or entity.canonical_name in seen:
                continue
            seen.add(entity.canonical_name)
            matches.append((min(positions), entity))

        matches.sort(key=lambda item: item[0])
        return [entity.to_dict() for _position, entity in matches]

    def _find_entity(self, *, game_id: str, name: str) -> Entity | None:
        if self.entity_registry is None:
            return None

        candidates = [entity for entity in self.entity_registry.entities if entity.game_id == game_id]
        normalized = normalize_entity_name(name)
        for entity in candidates:
            names = [entity.normalized_name, normalize_entity_name(entity.canonical_name)]
            names.extend(normalize_entity_name(alias) for alias in entity.aliases)
            if normalized in names:
                return entity

        if not candidates:
            return None
        return EntityRegistry(candidates, min_score=self.entity_registry.min_score).find_fuzzy(name)
