from omnilibrarian.rag.query_rewriting import rewrite_query
from omnilibrarian.entities.models import Entity
from omnilibrarian.entities.registry import EntityRegistry


def test_rewrite_query_maps_ukrainian_mixed_query_to_english_retrieval_terms():
    rewritten = rewrite_query("Порівняй мені fireball з молнією що завдає більше шкоди")

    assert rewritten.original_query == "Порівняй мені fireball з молнією що завдає більше шкоди"
    assert rewritten.retrieval_query == "compare fireball with Lightning Bolt damage"
    assert rewritten.was_rewritten is True
    assert "молнією->Lightning Bolt" in rewritten.rewrite_reasons


def test_rewrite_query_keeps_english_query_when_no_rules_match():
    rewritten = rewrite_query("Fireball damage")

    assert rewritten.original_query == "Fireball damage"
    assert rewritten.retrieval_query == "Fireball damage"
    assert rewritten.was_rewritten is False
    assert rewritten.rewrite_reasons == []


def test_rewrite_query_supports_common_ukrainian_damage_terms():
    rewritten = rewrite_query("що сильніше блискавка чи фаєрбол урон")

    assert rewritten.retrieval_query == "what stronger Lightning Bolt or Fireball damage"
    assert "блискавка->Lightning Bolt" in rewritten.rewrite_reasons
    assert "фаєрбол->Fireball" in rewritten.rewrite_reasons
    assert "урон->damage" in rewritten.rewrite_reasons


def test_rewrite_query_uses_entity_registry_for_typo_correction():
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Fireball",
                aliases=["fireball"],
            )
        ],
        min_score=88,
    )

    rewritten = rewrite_query("fireballll damage", entity_registry=registry)

    assert rewritten.retrieval_query == "Fireball damage"
    assert "fireballll->Fireball:fuzzy" in rewritten.rewrite_reasons


def test_rewrite_query_does_not_rewrite_stopword_to_similar_entity_name():
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

    rewritten = rewrite_query("Who is Astarion?", entity_registry=registry)

    assert rewritten.retrieval_query == "Who is Astarion"
    assert rewritten.rewrite_reasons == []


def test_rewrite_query_does_not_rewrite_blue_prince_generic_words_to_entities():
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

    assert rewrite_query("What is the Parlor room?", entity_registry=registry).retrieval_query == "What is the Parlor room"
    assert rewrite_query("How do blueprints work?", entity_registry=registry).retrieval_query == "How do blueprints work"
    assert (
        rewrite_query("What lore is in Blue Prince?", entity_registry=registry).retrieval_query
        == "What lore is in Blue Prince"
    )


def test_rewrite_query_maps_ukrainian_transliterated_entity_to_canonical_title():
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

    rewritten = rewrite_query("Хто такий Астаріон?", entity_registry=registry)

    assert rewritten.retrieval_query == "Хто такий Astarion"
    assert "Астаріон->Astarion:fuzzy" in rewritten.rewrite_reasons
