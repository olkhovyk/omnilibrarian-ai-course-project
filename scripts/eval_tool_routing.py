import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.entities.models import load_entities
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.evals.tool_routing import (
    load_tool_routing_golden,
    run_tool_routing_eval,
    write_tool_routing_report,
)
from omnilibrarian.knowledge import KnowledgeService
from omnilibrarian.tools import ToolRouter


class NullRetriever:
    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate tool routing against a golden set.")
    parser.add_argument("--golden", default="data/evals/bg3_tool_routing_golden.jsonl")
    parser.add_argument("--entities-path", default="data/processed/bg3/bg3_wiki_entities.json")
    parser.add_argument("--output", default="data/evals/bg3_tool_routing_results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_tool_routing_golden(args.golden)
    entities_path = Path(args.entities_path)
    entity_registry = EntityRegistry(load_entities(entities_path)) if entities_path.exists() else EntityRegistry([])
    service = KnowledgeService(retriever=NullRetriever(), entity_registry=entity_registry)
    router = ToolRouter(service)

    evaluated_cases, metrics = run_tool_routing_eval(router=router, cases=cases)
    write_tool_routing_report(args.output, cases=evaluated_cases, metrics=metrics)

    print("Tool routing eval")
    print(f"golden: {args.golden}")
    print(f"output: {args.output}")
    for name, value in metrics.items():
        if name.endswith(".total") or name == "total":
            print(f"{name}: {int(value)}")
        else:
            print(f"{name}: {value:.3f}")

    print("\nCases")
    for case in evaluated_cases:
        print(f"- {case['id']}: expected={case['expected_tool']} selected={case['selected_tool']} passed={case['passed']}")


if __name__ == "__main__":
    main()
