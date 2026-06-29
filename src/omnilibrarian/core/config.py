from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_env: str
    qdrant_url: str
    qdrant_collection: str
    llm_provider: str
    llm_model: str
    openai_api_key: str
    openrouter_api_key: str
    embedding_model: str
    embedding_device: str
    entity_registry_path: str
    warmup_on_startup: bool
    redis_url: str
    llm_cache_enabled: bool
    llm_cache_ttl_seconds: int
    rate_limit_enabled: bool
    rate_limit_requests_per_minute: int
    rate_limit_requests_per_day: int
    hybrid_retrieval_enabled: bool
    bm25_chunks_path: str
    bm25_extra_chunks_paths: str
    mcp_enabled: bool
    bg3_mcp_url: str
    blue_prince_mcp_url: str


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "omnilibrarian_chunks"),
        llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-4.1-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        embedding_device=os.getenv("EMBEDDING_DEVICE", "cuda"),
        entity_registry_path=os.getenv("ENTITY_REGISTRY_PATH", ""),
        warmup_on_startup=os.getenv("WARMUP_ON_STARTUP", "true").casefold() == "true",
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        llm_cache_enabled=os.getenv("LLM_CACHE_ENABLED", "true").casefold() == "true",
        llm_cache_ttl_seconds=int(os.getenv("LLM_CACHE_TTL_SECONDS", "86400")),
        rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").casefold() == "true",
        rate_limit_requests_per_minute=int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "10")),
        rate_limit_requests_per_day=int(os.getenv("RATE_LIMIT_REQUESTS_PER_DAY", "100")),
        hybrid_retrieval_enabled=os.getenv("HYBRID_RETRIEVAL_ENABLED", "true").casefold() == "true",
        bm25_chunks_path=os.getenv("BM25_CHUNKS_PATH", "data/processed/bg3/bg3_wiki_seed107_chunks.jsonl"),
        bm25_extra_chunks_paths=os.getenv("BM25_EXTRA_CHUNKS_PATHS", ""),
        mcp_enabled=os.getenv("MCP_ENABLED", "true").casefold() == "true",
        bg3_mcp_url=os.getenv("BG3_MCP_URL", "http://127.0.0.1:8765/mcp"),
        blue_prince_mcp_url=os.getenv("BLUE_PRINCE_MCP_URL", "http://127.0.0.1:8766/mcp"),
    )
