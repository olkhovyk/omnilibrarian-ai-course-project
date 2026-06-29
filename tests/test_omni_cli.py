import importlib.util
from pathlib import Path


def _load_omni_module():
    module_path = Path("scripts") / "omni.py"
    spec = importlib.util.spec_from_file_location("omni", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_omni_ingest_blue_prince_reddit_builds_short_command_from_config():
    omni = _load_omni_module()
    config = omni.load_pipeline_config(Path("configs/pipelines.yaml"))

    steps = omni.build_steps(["ingest", "blue_prince", "reddit"], config=config)

    assert [step.name for step in steps] == ["ingest_blue_prince_reddit"]
    command = steps[0].command
    assert "scripts/ingest.py" in command
    assert command[command.index("--game-id") + 1] == "blue_prince"
    assert command[command.index("--source") + 1] == "blue_prince_reddit"
    assert command[command.index("--processed-path") + 1] == "data/processed/blue_prince/blue_prince_reddit_chunks.jsonl"


def test_omni_index_blue_prince_reddit_rebuilds_only_that_source():
    omni = _load_omni_module()
    config = omni.load_pipeline_config(Path("configs/pipelines.yaml"))

    steps = omni.build_steps(["index", "blue_prince", "reddit"], config=config)

    assert [step.name for step in steps] == ["index_blue_prince_reddit"]
    command = steps[0].command
    assert command[command.index("--input") + 1] == "data/processed/blue_prince/blue_prince_reddit_chunks.jsonl"
    assert command[command.index("--source-id") + 1] == "blue_prince_reddit"
    assert command[command.index("--mode") + 1] == "rebuild-source"
    assert "--replace-game" not in command
    assert "--no-replace-game" not in command
    assert command[command.index("--device") + 1] == "cuda"
    assert "--allow-empty" in command


def test_omni_eval_blue_prince_answers_uses_answer_golden_and_bm25_chunks():
    omni = _load_omni_module()
    config = omni.load_pipeline_config(Path("configs/pipelines.yaml"))

    steps = omni.build_steps(["eval", "blue_prince", "answers"], config=config)

    assert [step.name for step in steps] == ["eval_blue_prince_answers"]
    command = steps[0].command
    assert "scripts/eval_answers.py" in command
    assert command[command.index("--golden") + 1] == "data/evals/blue_prince_answer_golden_v1.jsonl"
    assert command[command.index("--bm25-chunks-path") + 1] == "data/processed/blue_prince/blue_prince_wiki_chunks.jsonl"
    assert command[command.index("--bm25-extra-chunks-path") + 1] == "data/processed/blue_prince/blue_prince_reddit_chunks.jsonl"
    assert command[command.index("--output") + 1] == "data/evals/blue_prince_answer_results.json"


def test_omni_dev_starts_existing_single_command_runner():
    omni = _load_omni_module()
    config = omni.load_pipeline_config(Path("configs/pipelines.yaml"))

    steps = omni.build_steps(["dev"], config=config)

    assert [step.name for step in steps] == ["run_dev"]
    assert steps[0].command[1:] == ["scripts/run_dev.py"]
