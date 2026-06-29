import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "pipelines.yaml"


@dataclass(frozen=True)
class OmniStep:
    name: str
    command: list[str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Short OmniLibrarian command runner backed by configs/pipelines.yaml."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("dev", help="Start API, UI, and MCP servers with scripts/run_dev.py.")

    ingest = subparsers.add_parser("ingest", help="Fetch and process source documents.")
    ingest.add_argument("game_id")
    ingest.add_argument("source")
    ingest.add_argument("--max-documents", type=int, default=None)
    ingest.add_argument("--force-refresh", action="store_true")

    entities = subparsers.add_parser("entities", help="Build entity registry for a game.")
    entities.add_argument("game_id")
    entities.add_argument("--source", default=None, help="Source to build entities from. Defaults to primary BM25 source.")

    index = subparsers.add_parser("index", help="Index chunks into Qdrant.")
    index.add_argument("game_id")
    index.add_argument("source", nargs="?", default=None, help="Source to index. Omit to index all configured sources.")
    index.add_argument("--mode", choices=["rebuild-source", "append"], default="rebuild-source")

    eval_parser = subparsers.add_parser("eval", help="Run evals.")
    eval_parser.add_argument("game_id")
    eval_parser.add_argument("kind", choices=["retrieval", "tools", "answers", "all"])

    pipeline = subparsers.add_parser("pipeline", help="Run ingest, entities, index, and evals for a game.")
    pipeline.add_argument("game_id")
    pipeline.add_argument("--max-documents", type=int, default=None)
    pipeline.add_argument("--force-refresh", action="store_true")

    return parser.parse_args(argv)


def load_pipeline_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Pipeline config must be a mapping: {path}")
    return loaded


def build_steps(argv: list[str], *, config: dict[str, Any]) -> list[OmniStep]:
    args = parse_args(argv)
    return build_steps_from_args(args, config=config)


def build_steps_from_args(args: argparse.Namespace, *, config: dict[str, Any]) -> list[OmniStep]:
    if args.command == "dev":
        return [OmniStep("run_dev", [_python(), "scripts/run_dev.py"])]
    if args.command == "ingest":
        return [_build_ingest_step(args, config=config)]
    if args.command == "entities":
        return [_build_entities_step(args.game_id, source=args.source, config=config)]
    if args.command == "index":
        return _build_index_steps(args, config=config)
    if args.command == "eval":
        return _build_eval_steps(args.game_id, args.kind, config=config)
    if args.command == "pipeline":
        return _build_pipeline_steps(args, config=config)
    raise SystemExit(f"Unsupported command: {args.command}")


def run_steps(steps: list[OmniStep], *, dry_run: bool) -> None:
    for index, step in enumerate(steps, start=1):
        print(f"\n[{index}/{len(steps)}] {step.name}")
        print(_format_command(step.command))
        if not dry_run:
            subprocess.run(step.command, cwd=PROJECT_ROOT, check=True)


def _build_ingest_step(args: argparse.Namespace, *, config: dict[str, Any]) -> OmniStep:
    source = _source_config(config, args.game_id, args.source)
    command = [
        _python(),
        "scripts/ingest.py",
        "--game-id",
        args.game_id,
        "--source",
        source["source_id"],
        "--process",
        "--processed-path",
        source["chunks_path"],
    ]
    if "manifest_mode" in source:
        command.extend(["--manifest-mode", str(source["manifest_mode"])])
    if "request_delay_seconds" in source:
        command.extend(["--request-delay-seconds", str(source["request_delay_seconds"])])
    if "max_retries" in source:
        command.extend(["--max-retries", str(source["max_retries"])])
    if "retry_backoff_seconds" in source:
        command.extend(["--retry-backoff-seconds", str(source["retry_backoff_seconds"])])
    if args.max_documents is not None:
        command.extend(["--max-documents", str(args.max_documents)])
    if args.force_refresh:
        command.append("--force-refresh")
    return OmniStep(f"ingest_{args.game_id}_{args.source}", command)


def _build_entities_step(game_id: str, *, source: str | None, config: dict[str, Any]) -> OmniStep:
    game = _game_config(config, game_id)
    source_name = source or game.get("primary_bm25_source") or next(iter(game["sources"]))
    source_config = _source_config(config, game_id, source_name)
    return OmniStep(
        f"build_{game_id}_entities",
        [
            _python(),
            "scripts/build_entities.py",
            "--input",
            source_config["chunks_path"],
            "--output",
            game["entities_path"],
            "--game-id",
            game_id,
        ],
    )


def _build_index_steps(args: argparse.Namespace, *, config: dict[str, Any]) -> list[OmniStep]:
    game = _game_config(config, args.game_id)
    source_names = [args.source] if args.source else list(game["sources"])
    return [
        _build_index_step(
            args.game_id,
            source_name,
            mode=args.mode,
            config=config,
        )
        for source_name in source_names
    ]


def _build_index_step(
    game_id: str,
    source_name: str,
    *,
    mode: str,
    config: dict[str, Any],
) -> OmniStep:
    defaults = config.get("defaults", {})
    source = _source_config(config, game_id, source_name)
    command = [
        _python(),
        "scripts/index_chunks.py",
        "--input",
        source["chunks_path"],
        "--game-id",
        game_id,
        "--qdrant-url",
        defaults.get("qdrant_url", "http://localhost:6333"),
        "--collection",
        defaults.get("collection", "omnilibrarian_chunks"),
        "--model",
        defaults.get("embedding_model", "BAAI/bge-m3"),
        "--device",
        defaults.get("device", "cuda"),
        "--source-id",
        source["source_id"],
        "--mode",
        mode,
    ]
    if source.get("allow_empty"):
        command.append("--allow-empty")
    return OmniStep(f"index_{game_id}_{source_name}", command)


def _build_eval_steps(game_id: str, kind: str, *, config: dict[str, Any]) -> list[OmniStep]:
    if kind == "all":
        kinds = ["retrieval", "tools", "answers"]
    else:
        kinds = [kind]
    steps = []
    for selected_kind in kinds:
        if selected_kind == "answers" and "answer_golden" not in _game_config(config, game_id):
            continue
        steps.append(_build_eval_step(game_id, selected_kind, config=config))
    return steps


def _build_eval_step(game_id: str, kind: str, *, config: dict[str, Any]) -> OmniStep:
    defaults = config.get("defaults", {})
    game = _game_config(config, game_id)
    bm25_source = game.get("primary_bm25_source") or next(iter(game["sources"]))
    bm25_chunks_path = _source_config(config, game_id, bm25_source)["chunks_path"]
    bm25_extra_chunks_paths = _extra_bm25_chunks_paths(config, game_id, primary_source=bm25_source)
    common_retrieval_args = [
        "--game-id",
        game_id,
        "--entities-path",
        game["entities_path"],
        "--bm25-chunks-path",
        bm25_chunks_path,
        "--qdrant-url",
        defaults.get("qdrant_url", "http://localhost:6333"),
        "--collection",
        defaults.get("collection", "omnilibrarian_chunks"),
    ]
    for extra_path in bm25_extra_chunks_paths:
        common_retrieval_args.extend(["--bm25-extra-chunks-path", extra_path])
    if kind == "retrieval":
        return OmniStep(
            f"eval_{game_id}_retrieval",
            [
                _python(),
                "scripts/eval_retrieval.py",
                "--golden",
                game["retrieval_golden"],
                *common_retrieval_args,
                "--model",
                defaults.get("embedding_model", "BAAI/bge-m3"),
                "--device",
                defaults.get("device", "cuda"),
                "--output",
                game["retrieval_output"],
            ],
        )
    if kind == "tools":
        return OmniStep(
            f"eval_{game_id}_tools",
            [
                _python(),
                "scripts/eval_tool_routing.py",
                "--golden",
                game["tool_routing_golden"],
                "--entities-path",
                game["entities_path"],
                "--output",
                game["tool_routing_output"],
            ],
        )
    if kind == "answers":
        return OmniStep(
            f"eval_{game_id}_answers",
            [
                _python(),
                "scripts/eval_answers.py",
                "--golden",
                game["answer_golden"],
                *common_retrieval_args,
                "--embedding-model",
                defaults.get("embedding_model", "BAAI/bge-m3"),
                "--device",
                defaults.get("device", "cuda"),
                "--output",
                game["answer_output"],
            ],
        )
    raise SystemExit(f"Unsupported eval kind: {kind}")


def _build_pipeline_steps(args: argparse.Namespace, *, config: dict[str, Any]) -> list[OmniStep]:
    game = _game_config(config, args.game_id)
    steps: list[OmniStep] = []
    for source_name in game["sources"]:
        ingest_args = argparse.Namespace(
            game_id=args.game_id,
            source=source_name,
            max_documents=args.max_documents,
            force_refresh=args.force_refresh,
        )
        steps.append(_build_ingest_step(ingest_args, config=config))
    steps.append(_build_entities_step(args.game_id, source=None, config=config))
    for source_name in game["sources"]:
        steps.append(
            _build_index_step(
                args.game_id,
                source_name,
                mode="rebuild-source",
                config=config,
            )
        )
    steps.extend(_build_eval_steps(args.game_id, "all", config=config))
    return steps


def _game_config(config: dict[str, Any], game_id: str) -> dict[str, Any]:
    games = config.get("games", {})
    if game_id not in games:
        raise SystemExit(f"Unknown game in pipeline config: {game_id}")
    return games[game_id]


def _source_config(config: dict[str, Any], game_id: str, source_name: str) -> dict[str, Any]:
    game = _game_config(config, game_id)
    sources = game.get("sources", {})
    if source_name not in sources:
        raise SystemExit(f"Unknown source for {game_id}: {source_name}")
    return sources[source_name]


def _extra_bm25_chunks_paths(config: dict[str, Any], game_id: str, *, primary_source: str) -> list[str]:
    game = _game_config(config, game_id)
    source_names = game.get("bm25_sources") or [primary_source]
    return [
        _source_config(config, game_id, source_name)["chunks_path"]
        for source_name in source_names
        if source_name != primary_source
    ]


def _python() -> str:
    return sys.executable


def _format_command(command: list[str]) -> str:
    return " ".join(_quote_part(part) for part in command)


def _quote_part(part: str) -> str:
    if not part or any(char.isspace() for char in part):
        return f'"{part}"'
    return part


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_pipeline_config(Path(args.config))
    steps = build_steps_from_args(args, config=config)
    if not steps:
        raise SystemExit("No steps selected.")
    run_steps(steps, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
