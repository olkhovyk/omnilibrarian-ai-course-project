from omnilibrarian.evals.retrieval import RetrievalEvalCase, evaluate_retrieval_results, run_retrieval_eval


def test_evaluate_retrieval_results_computes_hit_rates_and_mrr():
    cases = [
        {
            "id": "case-1",
            "game_id": "bg3",
            "category": "spell",
            "expected_titles": ["Fireball"],
            "expected_source_ids": [],
            "expected_terms": ["8d6"],
            "latency_ms": 10,
            "results": [{"title": "Fireball", "game_id": "bg3"}, {"title": "Scroll of Fireball", "game_id": "bg3"}],
        },
        {
            "id": "case-2",
            "game_id": "bg3",
            "category": "spell",
            "expected_titles": ["Lightning Bolt"],
            "expected_source_ids": [],
            "expected_terms": ["Lightning"],
            "latency_ms": 30,
            "results": [
                {"title": "Fireball", "game_id": "blue_prince"},
                {"title": "Lightning Bolt", "game_id": "bg3", "text": "Lightning damage"},
            ],
        },
        {
            "id": "case-3",
            "game_id": "bg3",
            "category": "character",
            "expected_titles": ["Astarion"],
            "expected_source_ids": ["bg3_wiki"],
            "expected_terms": ["vampire"],
            "latency_ms": 20,
            "results": [{"title": "Fireball", "game_id": "bg3", "source_id": "bg3_wiki"}],
        },
    ]

    metrics = evaluate_retrieval_results(cases)

    assert metrics["total"] == 3
    assert metrics["hit_at_1"] == 1 / 3
    assert metrics["hit_at_3"] == 2 / 3
    assert metrics["hit_at_5"] == 2 / 3
    assert metrics["mrr"] == (1 + 0.5 + 0) / 3
    assert metrics["term_coverage_at_5"] == 1 / 3
    assert metrics["tenant_isolation"] == 2 / 3
    assert metrics["source_hit_at_5"] == 1.0
    assert metrics["avg_latency_ms"] == 20
    assert metrics["category.spell.hit_at_5"] == 1.0
    assert metrics["category.character.hit_at_5"] == 0.0


class FakeRetriever:
    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        assert query == "fireballll damage"
        assert game_id == "bg3"
        assert limit == 3
        return [
            {
                "title": "Fireball",
                "game_id": "bg3",
                "section": "Lead",
                "retrieval_query": "Fireball damage",
                "rewrite_reasons": ["fireballll->Fireball:fuzzy"],
            }
        ]


def test_run_retrieval_eval_records_rewrite_context_and_metrics():
    cases = [
        RetrievalEvalCase(
            id="fireball-typo",
            query="fireballll damage",
            game_id="bg3",
            expected_titles=["Fireball"],
            expected_source_ids=["bg3_wiki"],
        )
    ]

    evaluated_cases, metrics = run_retrieval_eval(retriever=FakeRetriever(), cases=cases, limit=3)

    assert metrics["hit_at_1"] == 1.0
    assert evaluated_cases[0]["top_titles"] == ["Fireball"]
    assert evaluated_cases[0]["retrieval_query"] == "Fireball damage"
    assert evaluated_cases[0]["rewrite_reasons"] == ["fireballll->Fireball:fuzzy"]
    assert evaluated_cases[0]["expected_source_ids"] == ["bg3_wiki"]
    assert evaluated_cases[0]["source_hit_at_5"] is False
    assert evaluated_cases[0]["hit_at_1"] is True
    assert evaluated_cases[0]["tenant_isolated"] is True
    assert isinstance(evaluated_cases[0]["latency_ms"], int)
