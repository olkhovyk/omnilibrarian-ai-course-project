def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    clean_text = text.strip()
    while start < len(clean_text):
        end = min(start + chunk_size, len(clean_text))
        chunks.append(clean_text[start:end])
        if end == len(clean_text):
            break
        start = end - overlap
    return chunks


def chunk_text_by_paragraph(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap_paragraphs: int = 1,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap_paragraphs < 0:
        raise ValueError("overlap_paragraphs cannot be negative")

    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    current: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(_join_paragraphs(current))
                current = _overlap_tail(current, overlap_paragraphs)
            chunks.extend(_chunk_long_paragraph(paragraph, chunk_size))
            continue

        candidate = _join_paragraphs([*current, paragraph])
        if current and len(candidate) > chunk_size:
            chunks.append(_join_paragraphs(current))
            current = [*_overlap_tail(current, overlap_paragraphs), paragraph]
        else:
            current.append(paragraph)

    if current:
        chunks.append(_join_paragraphs(current))

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    raw_paragraphs = normalized.split("\n\n")
    paragraphs = []
    for paragraph in raw_paragraphs:
        clean = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        if clean:
            paragraphs.append(clean)
    return paragraphs


def _chunk_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    sentences = _split_sentences(paragraph)
    if len(sentences) <= 1:
        return chunk_text(paragraph, chunk_size=chunk_size, overlap=min(100, chunk_size // 5))

    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                chunks.append(" ".join(current))
                current = []
            chunks.extend(chunk_text(sentence, chunk_size=chunk_size, overlap=min(100, chunk_size // 5)))
            continue

        candidate = " ".join([*current, sentence])
        if current and len(candidate) > chunk_size:
            chunks.append(" ".join(current))
            current = [sentence]
        else:
            current.append(sentence)

    if current:
        chunks.append(" ".join(current))
    return chunks


def _split_sentences(text: str) -> list[str]:
    sentences = []
    for sentence in re_split_sentences(text):
        clean = sentence.strip()
        if clean:
            sentences.append(clean)
    return sentences


def re_split_sentences(text: str) -> list[str]:
    import re

    return re.split(r"(?<=[.!?])\s+", text.strip())


def _join_paragraphs(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraphs)


def _overlap_tail(paragraphs: list[str], overlap_paragraphs: int) -> list[str]:
    if overlap_paragraphs == 0:
        return []
    return paragraphs[-overlap_paragraphs:]
