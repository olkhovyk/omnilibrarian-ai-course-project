from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path


@dataclass(frozen=True)
class RawDocument:
    doc_id: str
    game_id: str
    source_id: str
    source_url: str
    title: str
    text_en: str
    content_type: str
    fetched_at: str
    license: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "doc_id": self.doc_id,
            "game_id": self.game_id,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "title": self.title,
            "text_en": self.text_en,
            "content_type": self.content_type,
            "fetched_at": self.fetched_at,
            "license": self.license,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RawDocument":
        return cls(
            doc_id=data["doc_id"],
            game_id=data["game_id"],
            source_id=data["source_id"],
            source_url=data["source_url"],
            title=data["title"],
            text_en=data["text_en"],
            content_type=data["content_type"],
            fetched_at=data["fetched_at"],
            license=data.get("license"),
        )


def write_raw_document(path: str | Path, document: RawDocument) -> None:
    raw_path = Path(path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_raw_document(path: str | Path) -> RawDocument:
    return RawDocument.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def datetime_to_iso(value: datetime) -> str:
    return value.isoformat()
