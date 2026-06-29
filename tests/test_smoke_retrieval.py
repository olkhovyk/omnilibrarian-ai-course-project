import importlib.util
from pathlib import Path


def _load_smoke_retrieval_module():
    module_path = Path("scripts") / "smoke_retrieval.py"
    spec = importlib.util.spec_from_file_location("smoke_retrieval", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_format_result_prints_full_chunk_text_without_truncation():
    smoke_retrieval = _load_smoke_retrieval_module()
    long_text = "Fireball damage. " * 40

    output = smoke_retrieval.format_result(
        1,
        {
            "score": 0.9,
            "rerank_score": 1.29,
            "rerank_reasons": ["title_exact:fireball", "text_term:damage"],
            "original_query": "Порівняй мені fireball з молнією",
            "retrieval_query": "compare fireball with Lightning Bolt",
            "rewrite_reasons": ["молнією->Lightning Bolt"],
            "title": "Fireball",
            "section": "Lead",
            "content_type": "spell",
            "source_url": "https://bg3.wiki/wiki/Fireball",
            "text": long_text,
        },
    )

    assert long_text in output
    assert "#1 score=0.9000 rerank=1.2900" in output
    assert "reasons=title_exact:fireball, text_term:damage" in output
    assert "retrieval_query=compare fireball with Lightning Bolt" in output
    assert "rewrite_reasons=молнією->Lightning Bolt" in output
    assert not output.endswith("...")
