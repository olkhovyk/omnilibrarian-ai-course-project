from __future__ import annotations

import json
import re

from omnilibrarian.ingestion.documents import RawDocument
from omnilibrarian.ingestion.normalize import NormalizedDocument, NormalizedSection


class BluePrinceRedditNormalizer:
    def normalize(self, raw_document: RawDocument) -> NormalizedDocument:
        payload = json.loads(raw_document.text_en)
        sections = []
        post_text = _post_text(payload)
        if post_text:
            sections.append(
                NormalizedSection(
                    section="Post",
                    text=post_text,
                    spoiler_level=_spoiler_level(raw_document.content_type, post_text),
                )
            )

        comments_text = _comments_text(payload)
        if comments_text:
            sections.append(
                NormalizedSection(
                    section="Top comments",
                    text=comments_text,
                    spoiler_level=_spoiler_level(raw_document.content_type, comments_text),
                )
            )

        return NormalizedDocument(
            doc_id=raw_document.doc_id,
            game_id=raw_document.game_id,
            source_id=raw_document.source_id,
            source_url=raw_document.source_url,
            title=raw_document.title,
            content_type=raw_document.content_type,
            language="en",
            sections=sections,
        )


def normalize_blue_prince_reddit_document(raw_document: RawDocument) -> NormalizedDocument:
    return BluePrinceRedditNormalizer().normalize(raw_document)


def _post_text(payload: dict) -> str:
    parts = [
        f"Reddit post: {payload.get('title') or ''}",
        f"Author: u/{payload.get('author') or 'unknown'}",
        f"Score: {payload.get('score') or 0}",
        str(payload.get("selftext") or ""),
        f"Permalink: {payload.get('permalink') or ''}",
    ]
    return _clean_text("\n".join(part for part in parts if part))


def _comments_text(payload: dict) -> str:
    comments = payload.get("comments") or []
    blocks = []
    for index, comment in enumerate(comments, start=1):
        blocks.append(
            _clean_text(
                "\n".join(
                    [
                        f"Comment {index} by u/{comment.get('author') or 'unknown'}",
                        f"Score: {comment.get('score') or 0}",
                        str(comment.get("body") or ""),
                        f"Permalink: {comment.get('permalink') or ''}",
                    ]
                )
            )
        )
    return "\n\n".join(block for block in blocks if block)


def _spoiler_level(content_type: str, text: str) -> str:
    lowered = f"{content_type} {text}".casefold()
    if any(marker in lowered for marker in ("hint", "spoiler", "puzzle", "solution", "late game")):
        return "spoiler_heavy"
    return "standard"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
