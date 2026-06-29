import json
from pathlib import Path
from uuid import uuid4

from omnilibrarian.ingestion.documents import RawDocument, write_raw_document
from omnilibrarian.ingestion.normalize import process_raw_documents_to_chunks
from omnilibrarian.ingestion.sources.blue_prince_wiki_normalizer import (
    BluePrinceWikiNormalizer,
    normalize_blue_prince_wiki_document,
)


ROOMS_TEXT = """
Rooms are a central component of Blue Prince.
List of rooms
Room Number | Room | Gem Cost | Types | Rarity
5 | Parlor | None | Puzzle, Blueprint | Commonplace
46 | Room 46 | None | Blueprint, Objective | Rumored
References
Retrieved from "https://blueprince.wiki.gg/wiki/Rooms"
This page was last edited on 18 June 2025.
"""


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _raw_rooms() -> RawDocument:
    return RawDocument(
        doc_id="blue_prince_wiki:Rooms",
        game_id="blue_prince",
        source_id="blue_prince_wiki",
        source_url="https://blueprince.wiki.gg/wiki/Rooms",
        title="Rooms",
        text_en=ROOMS_TEXT,
        content_type="rooms",
        fetched_at="2026-06-06T10:00:00+00:00",
        license="CC BY-SA 4.0 unless otherwise noted",
    )


def test_normalizer_keeps_room_table_and_marks_spoiler_heavy_content():
    normalized = normalize_blue_prince_wiki_document(_raw_rooms())

    section_titles = [section.section for section in normalized.sections]
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "Lead" in section_titles
    assert "List of rooms" in section_titles
    assert "Parlor | None | Puzzle" in full_text
    assert "Room 46" in full_text
    assert "Retrieved from" not in full_text
    assert "This page was last edited" not in full_text
    assert any(section.spoiler_level == "spoiler_heavy" for section in normalized.sections)


def test_process_blue_prince_raw_documents_writes_chunks_with_game_id():
    test_dir = _workspace_test_dir()
    raw_path = test_dir / "raw" / "Rooms.json"
    processed_path = test_dir / "processed" / "chunks.jsonl"
    write_raw_document(raw_path, _raw_rooms())

    chunks = process_raw_documents_to_chunks(
        raw_paths=[raw_path],
        output_path=processed_path,
        normalizer=BluePrinceWikiNormalizer(),
        chunk_size=120,
        overlap=20,
    )

    assert chunks
    lines = [json.loads(line) for line in processed_path.read_text(encoding="utf-8").splitlines()]
    assert all(line["game_id"] == "blue_prince" for line in lines)
    assert all(line["source_id"] == "blue_prince_wiki" for line in lines)
    assert any(line["content_type"] == "rooms" for line in lines)
    assert any("Parlor" in line["text"] for line in lines)
