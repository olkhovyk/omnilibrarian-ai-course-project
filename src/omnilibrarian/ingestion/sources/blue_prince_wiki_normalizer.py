from __future__ import annotations

import re

from omnilibrarian.ingestion.documents import RawDocument
from omnilibrarian.ingestion.normalize import NormalizedDocument, NormalizedSection


BLOCKED_SECTIONS = {
    "contents",
    "gallery",
    "references",
    "external links",
    "navigation menu",
}

SPOILER_HEAVY_MARKERS = {
    "room 46",
    "ending",
    "post-credits",
    "spoiler",
    "late game",
    "lore",
}

FOOTER_MARKERS = [
    "Retrieved from",
    "Categories:",
    "This page was last edited",
    "Page content is under",
    "Cookies help us deliver",
]


class BluePrinceWikiNormalizer:
    def normalize(self, raw_document: RawDocument) -> NormalizedDocument:
        sections = self._split_sections(raw_document.text_en)
        normalized_sections = [
            NormalizedSection(
                section=section_title,
                text=section_text,
                spoiler_level=self._spoiler_level(section_title, section_text),
            )
            for section_title, section_text in sections
            if not self._is_blocked_section(section_title) and section_text.strip()
        ]
        return NormalizedDocument(
            doc_id=raw_document.doc_id,
            game_id=raw_document.game_id,
            source_id=raw_document.source_id,
            source_url=raw_document.source_url,
            title=raw_document.title,
            content_type=raw_document.content_type,
            language="en",
            sections=normalized_sections,
        )

    def _split_sections(self, text: str) -> list[tuple[str, str]]:
        lines = [line.strip() for line in text.splitlines()]
        sections: list[tuple[str, list[str]]] = []
        current_title = "Lead"
        current_lines: list[str] = []

        for line in lines:
            if not line:
                continue
            if self._looks_like_heading(line):
                if current_lines:
                    sections.append((current_title, current_lines))
                current_title = self._clean_heading(line)
                current_lines = []
            else:
                current_lines.append(self._clean_line(line))

        if current_lines:
            sections.append((current_title, current_lines))

        return [
            (title, self._clean_text(self._remove_footer_noise(" ".join(line for line in lines if line))))
            for title, lines in sections
        ]

    def _looks_like_heading(self, line: str) -> bool:
        clean = self._clean_heading(line)
        if len(clean) > 80 or clean.endswith("."):
            return False
        known = {
            "list of rooms",
            "spoilers within",
            "puzzle",
            "strategy",
            "notes",
            "effects",
            "items",
            "details",
            "trivia",
            "gallery",
            "references",
            "external links",
            "contents",
        }
        return clean.casefold() in known

    def _clean_heading(self, line: str) -> str:
        line = re.sub(r"\[.*?\]", "", line)
        return re.sub(r"\s+", " ", line).strip(" #")

    def _clean_line(self, line: str) -> str:
        line = re.sub(r"\[ *\d+ *\]", "", line)
        return self._clean_text(line)

    def _remove_footer_noise(self, text: str) -> str:
        first_marker_index = min(
            (index for marker in FOOTER_MARKERS if (index := text.find(marker)) != -1),
            default=-1,
        )
        if first_marker_index == -1:
            return text
        return text[:first_marker_index]

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _is_blocked_section(self, section: str) -> bool:
        return section.casefold() in BLOCKED_SECTIONS

    def _spoiler_level(self, section: str, text: str) -> str:
        lowered = f"{section} {text}".casefold()
        if any(marker in lowered for marker in SPOILER_HEAVY_MARKERS):
            return "spoiler_heavy"
        return "standard"


def normalize_blue_prince_wiki_document(raw_document: RawDocument) -> NormalizedDocument:
    return BluePrinceWikiNormalizer().normalize(raw_document)
