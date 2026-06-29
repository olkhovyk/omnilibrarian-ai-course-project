from omnilibrarian.answering import AnswerResult
from omnilibrarian.evals.answer import AnswerEvalCase, evaluate_answer_results, run_answer_eval


class FakeRetriever:
    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        assert game_id == "blue_prince"
        assert limit == 3
        return [
            {
                "title": "Room 46",
                "section": "Lead",
                "source_url": "https://blueprince.wiki.gg/wiki/Room_46",
                "text": "Room 46 is a special room.",
                "retrieval_query": query,
                "rewrite_reasons": [],
            }
        ]


class FakeAnswerGenerator:
    def generate(self, *, question: str, game_id: str, chunks: list[dict]) -> AnswerResult:
        return AnswerResult(
            answer="Room 46 is a special room in Blue Prince [1].",
            sources=[
                {
                    "id": 1,
                    "title": "Room 46",
                    "section": "Lead",
                    "url": "https://blueprince.wiki.gg/wiki/Room_46",
                }
            ],
            cache_status="miss",
        )


def test_run_answer_eval_records_answer_quality_signals():
    cases = [
        AnswerEvalCase(
            id="room-46",
            query="What is Room 46?",
            game_id="blue_prince",
            expected_source_titles=["Room 46"],
            expected_answer_terms=["Room 46", "special"],
            category="rooms",
        )
    ]

    rows, metrics = run_answer_eval(
        retriever=FakeRetriever(),
        answer_generator=FakeAnswerGenerator(),
        cases=cases,
        limit=3,
    )

    assert rows[0]["source_hit"] is True
    assert rows[0]["citation_present"] is True
    assert rows[0]["answer_term_coverage"] == 1.0
    assert rows[0]["insufficient_context"] is False
    assert rows[0]["retrieved_titles"] == ["Room 46"]
    assert metrics["grounded_answer_rate"] == 1.0
    assert metrics["category.rooms.grounded_answer_rate"] == 1.0


def test_evaluate_answer_results_penalizes_missing_citations_and_terms():
    metrics = evaluate_answer_results(
        [
            {
                "sources": [{"title": "Room 46"}],
                "expected_source_titles": ["Room 46"],
                "source_hit": True,
                "citation_present": False,
                "answer_term_coverage": 0.5,
                "insufficient_context": False,
                "allow_insufficient_context": False,
                "latency_ms": 10,
                "answer_latency_ms": 8,
            }
        ]
    )

    assert metrics["source_presence"] == 1.0
    assert metrics["source_hit"] == 1.0
    assert metrics["citation_presence"] == 0.0
    assert metrics["answer_term_coverage"] == 0.5
    assert metrics["grounded_answer_rate"] == 0.0
    assert metrics["no_unexpected_insufficient_context"] == 1.0


def test_evaluate_answer_results_supports_multilingual_expected_term_alternatives():
    class UkrainianPuzzleAnswerGenerator:
        def generate(self, *, question: str, game_id: str, chunks: list[dict]) -> AnswerResult:
            return AnswerResult(
                answer="Family Core - це головоломка у Blue Prince [1].",
                sources=[{"id": 1, "title": "Family Core Puzzle", "section": "Lead", "url": "https://example.test"}],
                cache_status="miss",
            )

    cases = [
        AnswerEvalCase(
            id="family-core",
            query="How does the Family Core Puzzle work?",
            game_id="blue_prince",
            expected_source_titles=["Family Core Puzzle"],
            expected_answer_terms=["Family Core", ["puzzle", "головолом"]],
            category="puzzles",
        )
    ]

    rows, metrics = run_answer_eval(
        retriever=FakeRetriever(),
        answer_generator=UkrainianPuzzleAnswerGenerator(),
        cases=cases,
        limit=3,
    )

    assert rows[0]["answer_term_coverage"] == 1.0
    assert metrics["grounded_answer_rate"] == 1.0
