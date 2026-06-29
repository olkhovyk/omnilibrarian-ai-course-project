import importlib.util
from pathlib import Path
from uuid import uuid4


def _load_index_chunks_module():
    module_path = Path("scripts") / "index_chunks.py"
    spec = importlib.util.spec_from_file_location("index_chunks", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_index_chunks_rebuilds_source_by_default(monkeypatch):
    index_chunks = _load_index_chunks_module()
    monkeypatch.setattr("sys.argv", ["index_chunks.py", "--input", "chunks.jsonl"])

    args = index_chunks.parse_args()

    assert args.mode == "rebuild-source"


def test_index_chunks_supports_append_mode(monkeypatch):
    index_chunks = _load_index_chunks_module()
    monkeypatch.setattr("sys.argv", ["index_chunks.py", "--input", "chunks.jsonl", "--mode", "append"])

    args = index_chunks.parse_args()

    assert args.mode == "append"


def test_index_chunks_requires_confirmation_for_rebuild_game():
    index_chunks = _load_index_chunks_module()

    try:
        index_chunks.validate_index_safety(
            mode="rebuild-game",
            game_id="blue_prince",
            source_id="blue_prince_wiki",
            confirm_delete_game=None,
        )
    except SystemExit as exc:
        assert "--confirm-delete-game blue_prince" in str(exc)
    else:
        raise AssertionError("Expected rebuild-game without confirmation to fail")


def test_index_chunks_infers_single_source_id_from_documents():
    index_chunks = _load_index_chunks_module()
    documents = [
        index_chunks.ChunkDocument(
            chunk_id="chunk-1",
            game_id="blue_prince",
            source_id="blue_prince_wiki",
            source_url="https://example.test",
            title="Rooms",
            content_type="room",
            language="en",
            section="Lead",
            spoiler_level="standard",
            text="Rooms text.",
        )
    ]

    source_id = index_chunks.resolve_source_id(documents=documents, requested_source_id=None)

    assert source_id == "blue_prince_wiki"


def test_index_chunks_allow_empty_skips_empty_optional_input(monkeypatch, capsys):
    index_chunks = _load_index_chunks_module()
    chunks_path = Path(".test_cache") / str(uuid4()) / "empty.jsonl"
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    chunks_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "index_chunks.py",
            "--input",
            str(chunks_path),
            "--game-id",
            "blue_prince",
            "--source-id",
            "blue_prince_reddit",
            "--allow-empty",
        ],
    )

    index_chunks.main()

    assert "skipping optional index step" in capsys.readouterr().out
