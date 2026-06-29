from __future__ import annotations

import logging
from pathlib import Path
import re

from omnilibrarian.core.config import Settings, load_settings
from omnilibrarian.entities.models import load_entities
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.knowledge.service import KnowledgeService
from omnilibrarian.rag.bm25 import BM25Retriever
from omnilibrarian.rag.documents import load_chunk_documents
from omnilibrarian.rag.embeddings import SentenceTransformerEmbeddingProvider
from omnilibrarian.rag.hybrid import HybridRetriever
from omnilibrarian.rag.qdrant_store import QdrantStore
from omnilibrarian.rag.retriever import Retriever


logger = logging.getLogger(__name__)


def build_knowledge_service(
    *,
    settings: Settings | None = None,
    retriever=None,
    entity_registry: EntityRegistry | None = None,
) -> KnowledgeService:
    settings = settings or load_settings()
    entity_registry = entity_registry or load_default_entity_registry(settings.entity_registry_path)
    retriever = retriever or build_retriever(settings=settings, entity_registry=entity_registry)
    return KnowledgeService(retriever=retriever, entity_registry=entity_registry)


def build_retriever(
    *,
    settings: Settings,
    embedding_provider=None,
    store=None,
    entity_registry: EntityRegistry | None = None,
):
    embedding_provider = embedding_provider or SentenceTransformerEmbeddingProvider(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
    )
    store = store or QdrantStore(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        vector_size=1,
    )

    if settings.hybrid_retrieval_enabled:
        documents = load_bm25_documents(settings=settings)
        if documents:
            logger.info("Hybrid retrieval enabled with %d BM25 chunk(s)", len(documents))
            return HybridRetriever(
                embedding_provider=embedding_provider,
                vector_store=store,
                lexical_retriever=BM25Retriever.from_documents(documents),
                entity_registry=entity_registry,
            )
        logger.warning(
            "Hybrid retrieval requested, but no BM25 chunks were found in configured paths: %s",
            _configured_bm25_paths(settings),
        )

    return Retriever(
        embedding_provider=embedding_provider,
        vector_store=store,
        entity_registry=entity_registry,
    )


def load_default_entity_registry(path: str) -> EntityRegistry | None:
    if not path:
        return None
    entity_path = Path(path)
    if not entity_path.exists():
        return None
    return EntityRegistry(load_entities(entity_path))


def load_bm25_documents(*, settings: Settings) -> list:
    documents = []
    for chunks_path in _configured_bm25_paths(settings):
        path = Path(chunks_path)
        if not path.exists():
            logger.warning("BM25 chunks file was not found: %s", path)
            continue
        loaded = load_chunk_documents(path)
        logger.info("Loaded %d BM25 chunk(s) from %s", len(loaded), path)
        documents.extend(loaded)
    return documents


def _configured_bm25_paths(settings: Settings) -> list[str]:
    paths = []
    if settings.bm25_chunks_path:
        paths.append(settings.bm25_chunks_path)
    if settings.bm25_extra_chunks_paths:
        paths.extend(
            path
            for path in re.split(r"[;,]", settings.bm25_extra_chunks_paths)
            if path.strip()
        )
    return paths
