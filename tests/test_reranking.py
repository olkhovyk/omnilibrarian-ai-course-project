from omnilibrarian.rag.reranking import is_comparative_query, rerank_results


def test_exact_title_match_boosts_fireball_above_unrelated_spell():
    results = [
        {
            "title": "Lightning Bolt",
            "text": "Lightning Bolt deals lightning damage.",
            "score": 0.7,
        },
        {
            "title": "Fireball",
            "text": "Fireball deals 8d6 Fire damage.",
            "score": 0.65,
        },
    ]

    reranked = rerank_results("Fireball damage", results, limit=2)

    assert [result["title"] for result in reranked] == ["Fireball", "Lightning Bolt"]
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]
    assert "title_exact:fireball" in reranked[0]["rerank_reasons"]


def test_partial_title_match_boosts_scroll_of_fireball():
    results = [
        {
            "title": "Eldritch Blast",
            "text": "Eldritch Blast deals force damage.",
            "score": 0.61,
        },
        {
            "title": "Scroll of Fireball",
            "text": "The scroll allows the user to cast Fireball.",
            "score": 0.6,
        },
    ]

    reranked = rerank_results("Fireball damage", results, limit=2)

    assert reranked[0]["title"] == "Scroll of Fireball"
    assert "title_token:fireball" in reranked[0]["rerank_reasons"]


def test_exact_entity_title_beats_semantically_related_character_page():
    results = [
        {
            "title": "Aelis Siryausius",
            "section": "Involvement",
            "text": "Aelis Siryausius can be encountered near Astarion during a related scene.",
            "score": 0.99,
        },
        {
            "title": "Astarion",
            "section": "Lead",
            "text": "Astarion Ancunin is an origin character and recruitable companion.",
            "score": 0.01,
        },
    ]

    reranked = rerank_results("Who is Astarion?", results, limit=2)

    assert reranked[0]["title"] == "Astarion"
    assert "title_exact:astarion" in reranked[0]["rerank_reasons"]


def test_definitional_query_prefers_lead_section_for_exact_title():
    results = [
        {
            "title": "Astarion",
            "section": "History",
            "text": "Astarion was a magistrate in Baldur's Gate before becoming a vampire spawn.",
            "score": 0.99,
        },
        {
            "title": "Astarion",
            "section": "Lead",
            "text": "Astarion Ancunin is an origin character and recruitable companion.",
            "score": 0.01,
        },
    ]

    reranked = rerank_results("Who is Astarion?", results, limit=2)

    assert reranked[0]["section"] == "Lead"
    assert "section_lead_for_definition" in reranked[0]["rerank_reasons"]


def test_definitional_query_diversifies_exact_title_sections():
    results = [
        {
            "title": "Astarion",
            "section": "History",
            "text": "History chunk one.",
            "score": 0.95,
        },
        {
            "title": "Astarion",
            "section": "History",
            "text": "History chunk two.",
            "score": 0.94,
        },
        {
            "title": "Astarion",
            "section": "History",
            "text": "History chunk three.",
            "score": 0.93,
        },
        {
            "title": "Astarion",
            "section": "Gameplay",
            "text": "Astarion can join the party as a companion.",
            "score": 0.72,
        },
        {
            "title": "Astarion",
            "section": "Approval",
            "text": "Astarion has approval and romance interactions.",
            "score": 0.71,
        },
    ]

    reranked = rerank_results("Who is Astarion?", results, limit=3)

    assert [result["section"] for result in reranked] == ["History", "Gameplay", "Approval"]
    assert any("section_diversity" in result["rerank_reasons"] for result in reranked[1:])


def test_candidates_without_title_matches_are_not_removed():
    results = [
        {
            "title": "Initiative",
            "text": "Fireball can use a Dexterity saving throw.",
            "score": 0.5,
        }
    ]

    reranked = rerank_results("Fireball damage", results, limit=5)

    assert len(reranked) == 1
    assert reranked[0]["title"] == "Initiative"
    assert "text_term:fireball" in reranked[0]["rerank_reasons"]


def test_comparative_query_detection_supports_english_and_ukrainian():
    assert is_comparative_query("Compare Fireball vs Lightning Bolt")
    assert is_comparative_query("Порівняй мені fireball з молнією")
    assert not is_comparative_query("Fireball damage")


def test_comparative_diversity_keeps_multiple_titles_when_scores_are_close():
    results = [
        {
            "title": "Fireball",
            "text": "Fireball deals 8d6 Fire damage.",
            "score": 0.7,
        },
        {
            "title": "Fireball",
            "text": "Fireball notes about visuals.",
            "score": 0.69,
        },
        {
            "title": "Lightning Bolt",
            "text": "Lightning Bolt deals 8d6 Lightning damage.",
            "score": 0.68,
        },
    ]

    reranked = rerank_results("Compare Fireball vs Lightning Bolt damage", results, limit=2)

    assert {result["title"] for result in reranked} == {"Fireball", "Lightning Bolt"}
    assert any("comparative_diversity" in result["rerank_reasons"] for result in reranked)
