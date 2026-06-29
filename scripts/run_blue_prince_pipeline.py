import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS_PATH = "data/processed/blue_prince/blue_prince_wiki_chunks.jsonl"
DEFAULT_ENTITIES_PATH = "data/processed/blue_prince/blue_prince_wiki_entities.json"
DEFAULT_RETRIEVAL_RESULTS_PATH = "data/evals/blue_prince_retrieval_results.json"
DEFAULT_TOOL_ROUTING_RESULTS_PATH = "data/evals/blue_prince_tool_routing_results.json"


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Blue Prince ingestion, indexing, and eval loop in the expected order."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-entities", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-retrieval-eval", action="store_true")
    parser.add_argument("--skip-tool-routing-eval", action="store_true")
    parser.add_argument("--manifest-mode", choices=["seed", "all"], default="all")
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--ttl-hours", type=int, default=168)
    parser.add_argument("--request-delay-seconds", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-backoff-seconds", type=float, default=15.0)
    parser.add_argument("--chunks-path", default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--entities-path", default=DEFAULT_ENTITIES_PATH)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--collection", default="omnilibrarian_chunks")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--retrieval-output", default=DEFAULT_RETRIEVAL_RESULTS_PATH)
    parser.add_argument("--tool-routing-output", default=DEFAULT_TOOL_ROUTING_RESULTS_PATH)
    return parser.parse_args()


def build_pipeline_steps(args: argparse.Namespace) -> list[PipelineStep]:
    python = sys.executable
    steps: list[PipelineStep] = []

    if not args.skip_ingest:
        ingest_command = [
            python,
            "scripts/ingest.py",
            "--game-id",
            "blue_prince",
            "--source",
            "blue_prince_wiki",
            "--manifest-mode",
            args.manifest_mode,
            "--ttl-hours",
            str(args.ttl_hours),
            "--request-delay-seconds",
            str(args.request_delay_seconds),
            "--max-retries",
            str(args.max_retries),
            "--retry-backoff-seconds",
            str(args.retry_backoff_seconds),
            "--process",
            "--processed-path",
            args.chunks_path,
        ]
        if args.max_documents is not None:
            ingest_command.extend(["--max-documents", str(args.max_documents)])
        if args.force_refresh:
            ingest_command.append("--force-refresh")
        steps.append(PipelineStep("ingest_blue_prince_wiki", ingest_command))

    if not args.skip_entities:
        steps.append(
            PipelineStep(
                "build_blue_prince_entities",
                [
                    python,
                    "scripts/build_entities.py",
                    "--input",
                    args.chunks_path,
                    "--output",
                    args.entities_path,
                    "--game-id",
                    "blue_prince",
                ],
            )
        )

    if not args.skip_index:
        steps.append(
            PipelineStep(
                "index_blue_prince_chunks",
                [
                    python,
                    "scripts/index_chunks.py",
                    "--input",
                    args.chunks_path,
                    "--game-id",
                    "blue_prince",
                    "--qdrant-url",
                    args.qdrant_url,
                    "--collection",
                    args.collection,
                    "--model",
                    args.model,
                    "--device",
                    args.device,
                    "--source-id",
                    "blue_prince_wiki",
                    "--mode",
                    "rebuild-source",
                ],
            )
        )

    if not args.skip_retrieval_eval:
        steps.append(
            PipelineStep(
                "eval_blue_prince_retrieval",
                [
                    python,
                    "scripts/eval_retrieval.py",
                    "--golden",
                    "data/evals/blue_prince_retrieval_golden_v1.jsonl",
                    "--game-id",
                    "blue_prince",
                    "--entities-path",
                    args.entities_path,
                    "--bm25-chunks-path",
                    args.chunks_path,
                    "--qdrant-url",
                    args.qdrant_url,
                    "--collection",
                    args.collection,
                    "--model",
                    args.model,
                    "--device",
                    args.device,
                    "--output",
                    args.retrieval_output,
                ],
            )
        )

    if not args.skip_tool_routing_eval:
        steps.append(
            PipelineStep(
                "eval_blue_prince_tool_routing",
                [
                    python,
                    "scripts/eval_tool_routing.py",
                    "--golden",
                    "data/evals/blue_prince_tool_routing_golden.jsonl",
                    "--entities-path",
                    args.entities_path,
                    "--output",
                    args.tool_routing_output,
                ],
            )
        )

    return steps


def run_steps(steps: list[PipelineStep], *, dry_run: bool) -> None:
    for index, step in enumerate(steps, start=1):
        print(f"\n[{index}/{len(steps)}] {step.name}")
        print(_format_command(step.command))
        if dry_run:
            continue
        subprocess.run(step.command, cwd=PROJECT_ROOT, check=True)


def _format_command(command: list[str]) -> str:
    return " ".join(_quote_part(part) for part in command)


def _quote_part(part: str) -> str:
    if not part or any(char.isspace() for char in part):
        return f'"{part}"'
    return part


def main() -> None:
    args = parse_args()
    steps = build_pipeline_steps(args)
    if not steps:
        raise SystemExit("No Blue Prince pipeline steps selected.")
    run_steps(steps, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
