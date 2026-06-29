from dataclasses import dataclass
from typing import Protocol

from omnilibrarian.ingestion.documents import RawDocument


@dataclass(frozen=True)
class SourceRef:
    doc_id: str
    source_url: str
    title: str
    content_type: str


class SourceAdapter(Protocol):
    source_id: str

    def fetch_manifest(self) -> list[SourceRef]:
        ...

    def fetch_document(self, ref: SourceRef) -> RawDocument:
        ...
