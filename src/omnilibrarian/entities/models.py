from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Entity:
    game_id: str
    canonical_name: str
    normalized_name: str
    content_type: str
    source_url: str
    aliases: list[str]

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "canonical_name": self.canonical_name,
            "normalized_name": self.normalized_name,
            "content_type": self.content_type,
            "source_url": self.source_url,
            "aliases": self.aliases,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        return cls(
            game_id=data["game_id"],
            canonical_name=data["canonical_name"],
            normalized_name=data["normalized_name"],
            content_type=data["content_type"],
            source_url=data["source_url"],
            aliases=list(data.get("aliases") or []),
        )


def write_entities(path: str | Path, entities: list[Entity]) -> None:
    entity_path = Path(path)
    entity_path.parent.mkdir(parents=True, exist_ok=True)
    entity_path.write_text(
        json.dumps([entity.to_dict() for entity in entities], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_entities(path: str | Path) -> list[Entity]:
    return [Entity.from_dict(item) for item in json.loads(Path(path).read_text(encoding="utf-8"))]
