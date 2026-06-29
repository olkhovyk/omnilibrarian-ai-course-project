from __future__ import annotations

import re

from omnilibrarian.ingestion.documents import RawDocument
from omnilibrarian.ingestion.normalize import NormalizedDocument, NormalizedSection


BLOCKED_SECTIONS = {
    "contents",
    "technical",
    "gallery",
    "notes",
    "notes and references",
    "visuals",
    "external links",
    "references",
}

PARENT_SECTIONS = {
    "overview",
    "description",
    "gameplay",
    "history",
    "involvement",
    "interactions & scenes",
}

SPOILER_HEAVY_SECTIONS = {
    "history",
    "involvement",
    "endings",
    "interactions & scenes",
    "act one",
    "act two",
    "act three",
}

FOOTER_MARKERS = [
    "Spotted an issue with this page?",
    "Retrieved from",
    "Categories :",
    "Navigation menu",
    "Personal tools",
    "This page was last edited",
    "Privacy policy",
    "About bg3.wiki",
]


class BG3WikiNormalizer:
    def normalize(self, raw_document: RawDocument) -> NormalizedDocument:
        sections = self._split_sections(raw_document.text_en)
        normalized_sections = [
            NormalizedSection(
                section=section_title,
                text=section_text,
                spoiler_level=self._spoiler_level(section_title),
            )
            for section_title, section_text in sections
            if not self._is_blocked_section(section_title, raw_document.content_type) and section_text.strip()
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
        current_parent: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if not line:
                continue
            if self._looks_like_heading(line):
                if current_lines:
                    sections.append((current_title, current_lines))
                title = self._clean_heading(line)
                if title.lower() in BLOCKED_SECTIONS:
                    current_parent = None
                    current_title = title
                elif title.lower() in PARENT_SECTIONS:
                    current_parent = title
                    current_title = title
                elif current_parent and current_parent.lower() in PARENT_SECTIONS:
                    current_title = f"{current_parent} > {title}"
                else:
                    current_title = title
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
        if len(clean) > 80:
            return False
        if clean.endswith("."):
            return False
        known = {
            "overview",
            "background",
            "starting class",
            "special features",
            "companion quest",
            "recruitment",
            "approval",
            "romance",
            "description",
            "appearance",
            "personality",
            "gameplay",
            "proficiencies",
            "unlockable bonuses",
            "technical",
            "gallery",
            "notes",
            "notes and references",
            "visuals",
            "external links",
            "contents",
            "history",
            "involvement",
        }
        return clean.lower() in known

    def _clean_heading(self, line: str) -> str:
        line = re.sub(r"\[.*?\]", "", line)
        line = re.sub(r"\s+", " ", line)
        return line.strip(" #")

    def _clean_line(self, line: str) -> str:
        line = re.sub(r"\[ *\d+ *\]", "", line)
        line = line.replace("⁠", " ")
        line = self._remove_technical_detail_blocks(line)
        line = self._remove_inline_technical_metadata(line)
        return self._clean_text(line)

    def _remove_technical_detail_blocks(self, text: str) -> str:
        markers = [
            "How to learn",
            "Where to find",
            "Notes",
            "Bugs",
            "External links",
        ]
        marker_pattern = "|".join(re.escape(marker) for marker in markers)
        text = re.sub(
            rf"\bTechnical details\b.*?(?=\b(?:{marker_pattern})\b|$)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            rf"\bSpell flags\b.*?(?=\b(?:{marker_pattern})\b|$)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _remove_inline_technical_metadata(self, text: str) -> str:
        text = re.sub(r"\bUID\s+[A-Za-z0-9_]+", "", text)
        text = re.sub(r"\bUUID\s+[A-Fa-f0-9-]{8,}", "", text)
        text = re.sub(r"\bStats\s+[A-Za-z0-9_]+", "", text)
        text = re.sub(r"\bEqp\.\s+[A-Za-z0-9_]+", "", text)
        return text

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

    def _is_blocked_section(self, section: str, content_type: str) -> bool:
        if content_type == "character" and section == "Lead":
            return True
        lowered = section.lower()
        parts = [part.strip().lower() for part in lowered.split(">")]
        return any(part in BLOCKED_SECTIONS for part in parts)

    def _spoiler_level(self, section: str) -> str:
        lowered = section.lower()
        if any(part in lowered for part in SPOILER_HEAVY_SECTIONS):
            return "spoiler_heavy"
        return "standard"


def normalize_bg3_wiki_document(raw_document: RawDocument) -> NormalizedDocument:
    return BG3WikiNormalizer().normalize(raw_document)
