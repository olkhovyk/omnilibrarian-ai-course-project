import json
from pathlib import Path
from uuid import uuid4

from omnilibrarian.ingestion.documents import RawDocument, write_raw_document
from omnilibrarian.ingestion.normalize import process_raw_documents_to_chunks
from omnilibrarian.ingestion.sources.bg3_wiki_normalizer import (
    BG3WikiNormalizer,
    normalize_bg3_wiki_document,
)


ASTARION_TEXT = """
Overview
Background
Astarion prowled the night as a vampire spawn for two centuries.
Starting class
Before he is recruited, Astarion is a level 1 rogue.
Recruitment
Astarion can be found west of the Nautiloid Wreck during Act One.
Technical
UID
S_Player_Astarion
UUID
c7c13742-bacd-460a-8f65-f864fe41f255
Gallery
Cover artwork
Notes and references
Some reference text
Personality
Astarion is charming, eloquent, cunning, witty, and practical.
"""


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _raw_astarion() -> RawDocument:
    return RawDocument(
        doc_id="bg3_wiki:Astarion",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Astarion",
        title="Astarion",
        text_en=ASTARION_TEXT,
        content_type="character",
        fetched_at="2026-05-29T09:00:00+00:00",
        license="CC BY-NC-SA 4.0 or CC BY-SA 4.0 where applicable",
    )


def test_normalizer_keeps_useful_character_sections_and_drops_boilerplate():
    normalized = normalize_bg3_wiki_document(_raw_astarion())

    section_titles = [section.section for section in normalized.sections]
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "Overview > Background" in section_titles
    assert "Overview > Starting class" in section_titles
    assert "Overview > Recruitment" in section_titles
    assert "Personality" in section_titles
    assert "Lead" not in section_titles
    assert "Technical" not in section_titles
    assert "Gallery" not in section_titles
    assert "Notes and references" not in section_titles
    assert "S_Player_Astarion" not in full_text
    assert "c7c13742-bacd-460a-8f65-f864fe41f255" not in full_text
    assert "Astarion can be found west" in full_text


def test_process_raw_documents_writes_chunk_jsonl_with_section_metadata():
    test_dir = _workspace_test_dir()
    raw_path = test_dir / "raw" / "Astarion.json"
    processed_path = test_dir / "processed" / "chunks.jsonl"
    write_raw_document(raw_path, _raw_astarion())

    chunks = process_raw_documents_to_chunks(
        raw_paths=[raw_path],
        output_path=processed_path,
        normalizer=BG3WikiNormalizer(),
        chunk_size=120,
        overlap=20,
    )

    assert processed_path.exists()
    assert chunks
    lines = [json.loads(line) for line in processed_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == len(chunks)
    assert all(line["game_id"] == "bg3" for line in lines)
    assert all(line["source_url"] == "https://bg3.wiki/wiki/Astarion" for line in lines)
    assert any(line["section"] == "Overview > Recruitment" for line in lines)
    assert all("S_Player_Astarion" not in line["text"] for line in lines)


def test_normalizer_removes_inline_technical_metadata_without_dropping_item_facts():
    raw = RawDocument(
        doc_id="bg3_wiki:Phalar_Aluve",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Phalar_Aluve",
        title="Phalar Aluve",
        text_en=(
            "Phalar Aluve is a rare Longsword.\n"
            "Properties One-handed damage 1d8 + 1 Slashing Price: 250 gp "
            "UID S_UND_SwordInStone_SwordReward "
            "UUID cc16c1cb-d355-47df-820a-33a83c42234b "
            "Stats UND_SwordInStone "
            "Special The holder of this item gains Performance +1."
        ),
        content_type="item",
        fetched_at="2026-05-29T09:00:00+00:00",
    )

    normalized = normalize_bg3_wiki_document(raw)
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "UID" not in full_text
    assert "UUID" not in full_text
    assert "UND_SwordInStone" not in full_text
    assert "One-handed damage" in full_text
    assert "Special The holder of this item gains Performance +1" in full_text


def test_normalizer_removes_spell_technical_details_without_dropping_damage():
    raw = RawDocument(
        doc_id="bg3_wiki:Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        title="Fireball",
        text_en=(
            "Fireball is a level 3 evocation spell.\n"
            "Description Shoot a bright flame from your fingers that explodes upon contact, "
            "Torching everything in the vicinity for 8d6 Fire damage.\n"
            "Technical details Spell flags CanAreaDamageEvade, HasSomaticComponent, "
            "HasVerbalComponent, IsHarmful, IsSpell, RangeIgnoreVerticalThreshold "
            "How to learn Classes: Wizard level 5."
        ),
        content_type="spell",
        fetched_at="2026-05-29T09:00:00+00:00",
    )

    normalized = normalize_bg3_wiki_document(raw)
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "8d6 Fire damage" in full_text
    assert "Technical details" not in full_text
    assert "Spell flags" not in full_text
    assert "CanAreaDamageEvade" not in full_text
    assert "How to learn" in full_text


def test_normalizer_drops_spell_notes_and_visuals_sections():
    raw = RawDocument(
        doc_id="bg3_wiki:Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        title="Fireball",
        text_en=(
            "Fireball is a level 3 evocation spell.\n"
            "Description Torching everything in the vicinity for 8d6 Fire damage.\n"
            "Notes\n"
            "The incantation for Fireball is Arde.\n"
            "Visuals\n"
            "https://bg3.wiki/wiki/File:Fireball-showcase.mp4\n"
        ),
        content_type="spell",
        fetched_at="2026-05-29T09:00:00+00:00",
    )

    normalized = normalize_bg3_wiki_document(raw)
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "8d6 Fire damage" in full_text
    assert "incantation" not in full_text
    assert "Fireball-showcase.mp4" not in full_text


def test_normalizer_removes_mediawiki_footer_navigation_noise():
    raw = RawDocument(
        doc_id="bg3_wiki:Scroll_of_Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Scroll_of_Fireball",
        title="Scroll of Fireball",
        text_en=(
            "Scroll of Fireball is a single-use scroll that allows the user to cast Fireball.\n"
            "Effect Action Deals 8d6 Fire to creatures in a radius.\n"
            "Retrieved from \" https://bg3.wiki/w/index.php?title=Scroll_of_Fireball&oldid=379008 \"\n"
            "Categories : Scrolls Rare items Navigation menu Personal tools Not logged in "
            "This page was last edited on 27 February 2026, at 23:27."
        ),
        content_type="item",
        fetched_at="2026-05-29T09:00:00+00:00",
    )

    normalized = normalize_bg3_wiki_document(raw)
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "Deals 8d6 Fire" in full_text
    assert "Retrieved from" not in full_text
    assert "Navigation menu" not in full_text
    assert "Personal tools" not in full_text
    assert "This page was last edited" not in full_text


def test_normalizer_removes_bg3_wiki_contribution_boilerplate():
    raw = RawDocument(
        doc_id="bg3_wiki:Scroll_of_Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Scroll_of_Fireball",
        title="Scroll of Fireball",
        text_en=(
            "Scroll of Fireball is a single-use scroll that allows the user to cast Fireball.\n"
            "Effect Action Deals 8d6 Fire to creatures in a radius.\n"
            "Spotted an issue with this page? Leave a comment! "
            "Note that your IP address will be publicly logged unless you create an account. "
            "See How to Contribute to get started."
        ),
        content_type="item",
        fetched_at="2026-05-29T09:00:00+00:00",
    )

    normalized = normalize_bg3_wiki_document(raw)
    full_text = "\n".join(section.text for section in normalized.sections)

    assert "Deals 8d6 Fire" in full_text
    assert "Spotted an issue" not in full_text
    assert "IP address" not in full_text
    assert "How to Contribute" not in full_text
