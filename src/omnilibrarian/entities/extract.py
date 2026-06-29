from __future__ import annotations

import re

from omnilibrarian.entities.models import Entity
from omnilibrarian.rag.documents import ChunkDocument


def build_entities_from_chunks(chunks: list[ChunkDocument]) -> list[Entity]:
    by_key: dict[tuple[str, str], ChunkDocument] = {}
    for chunk in chunks:
        key = (chunk.game_id, chunk.title)
        by_key.setdefault(key, chunk)

    entities = [
        Entity(
            game_id=chunk.game_id,
            canonical_name=chunk.title,
            normalized_name=normalize_entity_name(chunk.title),
            content_type=chunk.content_type,
            source_url=chunk.source_url,
            aliases=[normalize_entity_name(chunk.title)],
        )
        for chunk in by_key.values()
    ]
    return sorted(entities, key=lambda entity: (entity.game_id, entity.canonical_name.casefold()))


def normalize_entity_name(value: str) -> str:
    normalized = _transliterate_cyrillic(value).casefold().replace("_", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _transliterate_cyrillic(value: str) -> str:
    return value.translate(
        str.maketrans(
            {
                "А": "A",
                "а": "a",
                "Б": "B",
                "б": "b",
                "В": "V",
                "в": "v",
                "Г": "H",
                "г": "h",
                "Ґ": "G",
                "ґ": "g",
                "Д": "D",
                "д": "d",
                "Е": "E",
                "е": "e",
                "Є": "Ye",
                "є": "ye",
                "Ж": "Zh",
                "ж": "zh",
                "З": "Z",
                "з": "z",
                "И": "Y",
                "и": "y",
                "І": "I",
                "і": "i",
                "Ї": "Yi",
                "ї": "yi",
                "Й": "Y",
                "й": "y",
                "К": "K",
                "к": "k",
                "Л": "L",
                "л": "l",
                "М": "M",
                "м": "m",
                "Н": "N",
                "н": "n",
                "О": "O",
                "о": "o",
                "П": "P",
                "п": "p",
                "Р": "R",
                "р": "r",
                "С": "S",
                "с": "s",
                "Т": "T",
                "т": "t",
                "У": "U",
                "у": "u",
                "Ф": "F",
                "ф": "f",
                "Х": "Kh",
                "х": "kh",
                "Ц": "Ts",
                "ц": "ts",
                "Ч": "Ch",
                "ч": "ch",
                "Ш": "Sh",
                "ш": "sh",
                "Щ": "Shch",
                "щ": "shch",
                "Ь": "",
                "ь": "",
                "Ю": "Yu",
                "ю": "yu",
                "Я": "Ya",
                "я": "ya",
            }
        )
    )
