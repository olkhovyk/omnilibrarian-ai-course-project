from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Protocol

from omnilibrarian.ingestion.documents import read_raw_document
from omnilibrarian.rag.chunking import chunk_text_by_paragraph


@dataclass(frozen=True)
class NormalizedSection:
    section: str
    text: str
    spoiler_level: str


@dataclass(frozen=True)
class NormalizedDocument:
    doc_id: str
    game_id: str
    source_id: str
    source_url: str
    title: str
    content_type: str
    language: str
    sections: list[NormalizedSection]


@dataclass(frozen=True)
class DocumentChunk:
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

    def to_dict(self) -> dict[str, str]:
        return {
            "chunk_id": self.chunk_id,
            "game_id": self.game_id,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "title": self.title,
            "content_type": self.content_type,
            "language": self.language,
            "section": self.section,
            "spoiler_level": self.spoiler_level,
            "text": self.text,
        }


class DocumentNormalizer(Protocol):
    def normalize(self, raw_document) -> NormalizedDocument:
        ...


def document_to_chunks(
    document: NormalizedDocument,
    *,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    chunk_number = 1
    for section in document.sections:
        overlap_paragraphs = 1 if overlap > 0 else 0
        for text in chunk_text_by_paragraph(
            section.text,
            chunk_size=chunk_size,
            overlap_paragraphs=overlap_paragraphs,
        ):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.doc_id}:{_slug(section.section)}:{chunk_number:04d}",
                    game_id=document.game_id,
                    source_id=document.source_id,
                    source_url=document.source_url,
                    title=document.title,
                    content_type=document.content_type,
                    language=document.language,
                    section=section.section,
                    spoiler_level=section.spoiler_level,
                    text=text,
                )
            )
            chunk_number += 1
    return chunks


def process_raw_documents_to_chunks(
    *,
    raw_paths: list[str | Path],
    output_path: str | Path,
    normalizer: DocumentNormalizer,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[DocumentChunk]:
    all_chunks: list[DocumentChunk] = []
    for raw_path in raw_paths:
        raw_document = read_raw_document(raw_path)
        normalized = normalizer.normalize(raw_document)
        all_chunks.extend(document_to_chunks(normalized, chunk_size=chunk_size, overlap=overlap))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n" for chunk in all_chunks),
        encoding="utf-8",
    )
    return all_chunks


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "section"
