from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import math
import re

from omnilibrarian.rag.documents import ChunkDocument


class BM25Retriever:
    def __init__(self, documents: list[ChunkDocument], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.document_tokens = [_tokenize(_index_text(document)) for document in documents]
        self.document_lengths = [len(tokens) for tokens in self.document_tokens]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths) if self.document_lengths else 0.0
        )
        self.term_frequencies = [Counter(tokens) for tokens in self.document_tokens]
        self.document_frequencies = _document_frequencies(self.document_tokens)
        self.total_documents = len(documents)

    @classmethod
    def from_documents(cls, documents: list[ChunkDocument]) -> "BM25Retriever":
        return cls(documents)

    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        query_tokens = _tokenize(query)
        if not query_tokens or not self.documents:
            return []

        scored: list[tuple[float, ChunkDocument]] = []
        for index, document in enumerate(self.documents):
            if document.game_id != game_id:
                continue
            score = self._score_document(query_tokens, index)
            if score > 0:
                scored.append((score, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [_payload(document, score) for score, document in scored[:limit]]

    def _score_document(self, query_tokens: list[str], index: int) -> float:
        score = 0.0
        frequencies = self.term_frequencies[index]
        document_length = self.document_lengths[index]
        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if frequency == 0:
                continue
            idf = self._idf(token)
            denominator = frequency + self.k1 * (
                1 - self.b + self.b * document_length / max(self.average_document_length, 1.0)
            )
            score += idf * frequency * (self.k1 + 1) / denominator
        return score

    def _idf(self, token: str) -> float:
        containing_documents = self.document_frequencies.get(token, 0)
        return math.log(1 + (self.total_documents - containing_documents + 0.5) / (containing_documents + 0.5))


def _document_frequencies(document_tokens: list[list[str]]) -> dict[str, int]:
    frequencies: dict[str, int] = defaultdict(int)
    for tokens in document_tokens:
        for token in set(tokens):
            frequencies[token] += 1
    return dict(frequencies)


def _index_text(document: ChunkDocument) -> str:
    title_boost = " ".join([document.title] * 4)
    section_boost = " ".join([document.section] * 2)
    return f"{title_boost} {section_boost} {document.content_type} {document.text}"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE)


def _payload(document: ChunkDocument, score: float) -> dict:
    payload = asdict(document)
    payload["score"] = _normalize_score(score)
    payload["bm25_score"] = score
    payload["retrieval_source"] = "bm25"
    payload["retrieval_sources"] = ["bm25"]
    return payload


def _normalize_score(score: float) -> float:
    return score / (score + 1.0)
