from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ChunkDocument:
    chunk_id: str
    game_id: str
    source_id: str
    source_url: str
    title: str
    content_type: str
    language: str
    section: str
    spoiler_level: str
    text: str

    @classmethod
    def from_dict(cls, data: dict) -> "ChunkDocument":
        return cls(
            chunk_id=data["chunk_id"],
            game_id=data["game_id"],
            source_id=data["source_id"],
            source_url=data["source_url"],
            title=data["title"],
            content_type=data["content_type"],
            language=data["language"],
            section=data["section"],
            spoiler_level=data.get("spoiler_level", "standard"),
            text=data["text"],
        )


def load_chunk_documents(path: str | Path) -> list[ChunkDocument]:
    documents: list[ChunkDocument] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                documents.append(ChunkDocument.from_dict(json.loads(line)))
    return documents
