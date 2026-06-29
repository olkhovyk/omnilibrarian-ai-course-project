from omnilibrarian.rag.chunking import chunk_text, chunk_text_by_paragraph


def test_paragraph_chunking_keeps_short_paragraphs_intact():
    text = "First paragraph about Fireball.\n\nSecond paragraph about damage.\n\nThird paragraph about saves."

    chunks = chunk_text_by_paragraph(text, chunk_size=80, overlap_paragraphs=1)

    assert chunks == [
        "First paragraph about Fireball.\n\nSecond paragraph about damage.",
        "Second paragraph about damage.\n\nThird paragraph about saves.",
    ]


def test_paragraph_chunking_splits_very_long_paragraph_with_character_fallback():
    long_paragraph = "Fireball " * 80

    chunks = chunk_text_by_paragraph(long_paragraph, chunk_size=120, overlap_paragraphs=0)

    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks[:-1])


def test_long_paragraph_fallback_prefers_sentence_boundaries():
    text = (
        "Fireball is a powerful evocation spell. "
        "It deals fire damage in a large area. "
        "Creatures can attempt a Dexterity saving throw."
    )

    chunks = chunk_text_by_paragraph(text, chunk_size=90, overlap_paragraphs=0)

    assert chunks == [
        "Fireball is a powerful evocation spell. It deals fire damage in a large area.",
        "Creatures can attempt a Dexterity saving throw.",
    ]


def test_character_chunker_still_supports_simple_fallback():
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]
