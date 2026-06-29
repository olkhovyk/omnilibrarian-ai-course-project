from omnilibrarian.evals.tool_routing import (
    ToolRoutingEvalCase,
    evaluate_tool_routing_results,
    run_tool_routing_eval,
)


class Selection:
    def __init__(self, tool: str, arguments: dict | None = None) -> None:
        self.tool = tool
        self.arguments = arguments or {}


class FakeRouter:
    def select(self, *, game_id: str, query: str):
        assert game_id == "bg3"
        if "Compare" in query:
            return Selection("compare_bg3_spells", {"spell_a": "Fireball", "spell_b": "Lightning Bolt"})
        if "companions" in query:
            return Selection("list_bg3_companions", {"limit": 50})
        return None


def test_run_tool_routing_eval_records_selection_and_metrics():
    cases = [
        ToolRoutingEvalCase(
            id="compare-fire-lightning",
            query="Compare Fireball and Lightning Bolt",
            game_id="bg3",
            expected_tool="compare_bg3_spells",
            category="comparison",
        ),
        ToolRoutingEvalCase(
            id="list-companions",
            query="List all companions",
            game_id="bg3",
            expected_tool="list_bg3_companions",
            category="list",
        ),
        ToolRoutingEvalCase(
            id="plain-question",
            query="Who is Astarion?",
            game_id="bg3",
            expected_tool=None,
            category="direct_answer",
        ),
    ]

    rows, metrics = run_tool_routing_eval(router=FakeRouter(), cases=cases)

    assert metrics["total"] == 3
    assert metrics["accuracy"] == 1.0
    assert metrics["category.comparison.accuracy"] == 1.0
    assert rows[0]["selected_tool"] == "compare_bg3_spells"
    assert rows[1]["arguments"] == {"limit": 50}
    assert rows[2]["selected_tool"] is None
    assert isinstance(rows[0]["latency_ms"], int)


def test_evaluate_tool_routing_results_computes_category_accuracy():
    metrics = evaluate_tool_routing_results(
        [
            {"category": "comparison", "passed": True, "latency_ms": 10},
            {"category": "comparison", "passed": False, "latency_ms": 20},
            {"category": "list", "passed": True, "latency_ms": 30},
        ]
    )

    assert metrics["total"] == 3
    assert metrics["accuracy"] == 2 / 3
    assert metrics["avg_latency_ms"] == 20
    assert metrics["category.comparison.accuracy"] == 0.5
    assert metrics["category.list.accuracy"] == 1.0
