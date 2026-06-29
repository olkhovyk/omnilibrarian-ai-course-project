from pathlib import Path
from uuid import uuid4

from omnilibrarian.entities.extract import build_entities_from_chunks, normalize_entity_name
from omnilibrarian.entities.models import Entity, load_entities, write_entities
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.rag.documents import ChunkDocument


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_build_entities_from_chunks_groups_unique_titles():
    chunks = [
        ChunkDocument(
            chunk_id="1",
            game_id="bg3",
            source_id="bg3_wiki",
            source_url="https://bg3.wiki/wiki/Fireball",
            title="Fireball",
            content_type="spell",
            language="en",
            section="Lead",
            spoiler_level="standard",
            text="Fireball deals damage.",
        ),
        ChunkDocument(
            chunk_id="2",
            game_id="bg3",
            source_id="bg3_wiki",
            source_url="https://bg3.wiki/wiki/Fireball",
            title="Fireball",
            content_type="spell",
            language="en",
            section="How to learn",
            spoiler_level="standard",
            text="Wizards can learn Fireball.",
        ),
        ChunkDocument(
            chunk_id="3",
            game_id="bg3",
            source_id="bg3_wiki",
            source_url="https://bg3.wiki/wiki/Lightning_Bolt",
            title="Lightning Bolt",
            content_type="spell",
            language="en",
            section="Lead",
            spoiler_level="standard",
            text="Lightning Bolt deals damage.",
        ),
    ]

    entities = build_entities_from_chunks(chunks)

    assert entities == [
        Entity(
            game_id="bg3",
            canonical_name="Fireball",
            normalized_name="fireball",
            content_type="spell",
            source_url="https://bg3.wiki/wiki/Fireball",
            aliases=["fireball"],
        ),
        Entity(
            game_id="bg3",
            canonical_name="Lightning Bolt",
            normalized_name="lightning bolt",
            content_type="spell",
            source_url="https://bg3.wiki/wiki/Lightning_Bolt",
            aliases=["lightning bolt"],
        ),
    ]


def test_entities_round_trip_json():
    path = _workspace_test_dir() / "entities.json"
    entities = [
        Entity(
            game_id="bg3",
            canonical_name="Fireball",
            normalized_name="fireball",
            content_type="spell",
            source_url="https://bg3.wiki/wiki/Fireball",
            aliases=["fireball"],
        )
    ]

    write_entities(path, entities)

    assert load_entities(path) == entities


def test_entity_registry_fuzzy_matches_typos_with_rapidfuzz():
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Fireball",
                aliases=["fireball"],
            ),
            Entity(
                game_id="bg3",
                canonical_name="Lightning Bolt",
                normalized_name="lightning bolt",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Lightning_Bolt",
                aliases=["lightning bolt"],
            ),
            Entity(
                game_id="bg3",
                canonical_name="Damage Types",
                normalized_name="damage types",
                content_type="mechanic",
                source_url="https://bg3.wiki/wiki/Damage_Types",
                aliases=["damage types"],
            ),
        ],
        min_score=88,
    )

    assert registry.find_fuzzy("fireballll").canonical_name == "Fireball"
    assert registry.find_fuzzy("lightnign bolt").canonical_name == "Lightning Bolt"
    assert registry.find_fuzzy("damage") is None
    assert registry.find_fuzzy("is") is None
    assert registry.find_fuzzy("who") is None


def test_entity_registry_does_not_fuzzy_match_short_stopwords_to_entities():
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Aelis Siryasius",
                normalized_name="aelis siryasius",
                content_type="character",
                source_url="https://bg3.wiki/wiki/Aelis_Siryasius",
                aliases=["aelis siryasius"],
            ),
            Entity(
                game_id="bg3",
                canonical_name="Astarion",
                normalized_name="astarion",
                content_type="character",
                source_url="https://bg3.wiki/wiki/Astarion",
                aliases=["astarion"],
            ),
        ],
        min_score=88,
    )

    assert registry.find_fuzzy("is") is None
    assert registry.find_fuzzy("Who") is None
    assert registry.find_fuzzy("Astarion").canonical_name == "Astarion"


def test_entity_registry_does_not_fuzzy_match_blue_prince_generic_terms_to_page_titles():
    registry = EntityRegistry(
        [
            Entity(
                game_id="blue_prince",
                canonical_name="Ballroom",
                normalized_name="ballroom",
                content_type="rooms",
                source_url="https://blueprince.wiki.gg/wiki/Ballroom",
                aliases=["ballroom"],
            ),
            Entity(
                game_id="blue_prince",
                canonical_name="Network",
                normalized_name="network",
                content_type="mechanics",
                source_url="https://blueprince.wiki.gg/wiki/Network",
                aliases=["network"],
            ),
            Entity(
                game_id="blue_prince",
                canonical_name="Blue Prince",
                normalized_name="blue prince",
                content_type="mechanics",
                source_url="https://blueprince.wiki.gg/wiki/Blue_Prince",
                aliases=["blue prince"],
            ),
        ],
        min_score=88,
    )

    assert registry.find_fuzzy("room") is None
    assert registry.find_fuzzy("work") is None
    assert registry.find_fuzzy("Blue") is None
    assert registry.find_fuzzy("Prince") is None


def test_entity_registry_matches_ukrainian_transliterated_entity_names():
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Astarion",
                normalized_name="astarion",
                content_type="character",
                source_url="https://bg3.wiki/wiki/Astarion",
                aliases=["astarion"],
            )
        ],
        min_score=88,
    )

    assert normalize_entity_name("Астаріон") == "astarion"
    assert registry.find_fuzzy("Астаріон").canonical_name == "Astarion"
    assert registry.find_fuzzy("Астаріона").canonical_name == "Astarion"
