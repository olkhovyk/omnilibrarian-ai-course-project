import argparse
import importlib.util
from pathlib import Path


def _load_pipeline_module():
    module_path = Path("scripts") / "run_blue_prince_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_blue_prince_pipeline", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _args(**overrides):
    values = {
        "dry_run": False,
        "skip_ingest": False,
        "skip_entities": False,
        "skip_index": False,
        "skip_retrieval_eval": False,
        "skip_tool_routing_eval": False,
        "manifest_mode": "all",
        "max_documents": None,
        "force_refresh": False,
        "ttl_hours": 168,
        "request_delay_seconds": 1.0,
        "max_retries": 5,
        "retry_backoff_seconds": 15.0,
        "chunks_path": "data/processed/blue_prince/blue_prince_wiki_chunks.jsonl",
        "entities_path": "data/processed/blue_prince/blue_prince_wiki_entities.json",
        "qdrant_url": "http://localhost:6333",
        "collection": "omnilibrarian_chunks",
        "device": "cuda",
        "model": "BAAI/bge-m3",
        "retrieval_output": "data/evals/blue_prince_retrieval_results.json",
        "tool_routing_output": "data/evals/blue_prince_tool_routing_results.json",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_blue_prince_pipeline_builds_expected_default_step_order():
    pipeline = _load_pipeline_module()

    steps = pipeline.build_pipeline_steps(_args())

    assert [step.name for step in steps] == [
        "ingest_blue_prince_wiki",
        "build_blue_prince_entities",
        "index_blue_prince_chunks",
        "eval_blue_prince_retrieval",
        "eval_blue_prince_tool_routing",
    ]
    assert "blue_prince_wiki" in steps[0].command
    assert steps[0].command[steps[0].command.index("--manifest-mode") + 1] == "all"
    assert steps[0].command[steps[0].command.index("--request-delay-seconds") + 1] == "1.0"
    assert steps[0].command[steps[0].command.index("--max-retries") + 1] == "5"
    assert steps[2].command[steps[2].command.index("--game-id") + 1] == "blue_prince"
    assert steps[3].command[steps[3].command.index("--game-id") + 1] == "blue_prince"


def test_blue_prince_pipeline_supports_fast_limited_smoke_mode():
    pipeline = _load_pipeline_module()

    steps = pipeline.build_pipeline_steps(
        _args(
            manifest_mode="seed",
            max_documents=5,
            skip_index=True,
            skip_retrieval_eval=True,
        )
    )

    assert [step.name for step in steps] == [
        "ingest_blue_prince_wiki",
        "build_blue_prince_entities",
        "eval_blue_prince_tool_routing",
    ]
    ingest_command = steps[0].command
    assert ingest_command[ingest_command.index("--manifest-mode") + 1] == "seed"
    assert ingest_command[ingest_command.index("--max-documents") + 1] == "5"


def test_blue_prince_pipeline_dry_run_does_not_execute_subprocess(monkeypatch, capsys):
    pipeline = _load_pipeline_module()
    calls = []

    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    pipeline.run_steps(
        [pipeline.PipelineStep("example", ["python", "scripts/example.py"])],
        dry_run=True,
    )

    assert calls == []
    assert "scripts/example.py" in capsys.readouterr().out
