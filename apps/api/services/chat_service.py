from __future__ import annotations

import json
import time
import logging

from omnilibrarian.answering import AnswerGenerator
from omnilibrarian.cache.llm_cache import NullLLMCache, build_redis_llm_cache
from omnilibrarian.core.config import load_settings
from omnilibrarian.llm.openai_provider import OpenAIProvider
from omnilibrarian.llm.openrouter_provider import OpenRouterProvider
from omnilibrarian.graph.workflow import run_chat_workflow, run_context_workflow
from omnilibrarian.knowledge import KnowledgeService
from omnilibrarian.knowledge.factory import build_retriever, load_default_entity_registry
from omnilibrarian.memory import InMemorySessionStore
from omnilibrarian.mcp_clients import BG3MCPClient, BluePrinceMCPClient, MCPClientRegistry
from omnilibrarian.routing import GameDetector
from omnilibrarian.tenants.registry import load_tenant_registry


logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        *,
        retriever,
        answer_generator: AnswerGenerator,
        knowledge_service=None,
        mcp_client=None,
        session_store=None,
        game_detector=None,
    ) -> None:
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.knowledge_service = knowledge_service
        self.mcp_client = mcp_client
        self.session_store = session_store or InMemorySessionStore()
        self.game_detector = game_detector or _build_default_game_detector()
        self.is_warm = False

    def warmup(self) -> None:
        self.retriever.search("Fireball damage", game_id="bg3", limit=1)
        self.is_warm = True

    def answer(self, *, message: str, session_id: str, game_id: str | None) -> dict:
        started = time.perf_counter()
        history = self.session_store.get_history(session_id)
        detection = self.game_detector.detect(message=message, explicit_game_id=game_id)
        state = run_chat_workflow(
            {
                "original_query": message,
                "session_id": session_id,
                "game_id": detection.game_id,
                "history": history,
                "trace": [detection.to_trace()],
            },
            retriever=self.retriever,
            answer_generator=self.answer_generator,
            knowledge_service=self.knowledge_service,
            mcp_client=self.mcp_client,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        response = {
            "answer": state.get("answer", ""),
            "game_id": state.get("detected_game_id", game_id or "bg3"),
            "intent": state.get("intent"),
            "sources": state.get("sources", []),
            "tool_calls": state.get("tool_calls", []),
            "trace": state.get("trace", []),
            "latency_ms": latency_ms,
        }
        self._append_successful_turn(session_id=session_id, message=message, answer=response["answer"])
        return response

    def stream_answer(self, *, message: str, session_id: str, game_id: str | None):
        started = time.perf_counter()
        history = self.session_store.get_history(session_id)
        detection = self.game_detector.detect(message=message, explicit_game_id=game_id)
        state = run_context_workflow(
            {
                "original_query": message,
                "session_id": session_id,
                "game_id": detection.game_id,
                "history": history,
                "trace": [detection.to_trace()],
            },
            retriever=self.retriever,
            knowledge_service=self.knowledge_service,
            mcp_client=self.mcp_client,
        )

        if state.get("answer") and not state.get("retrieved_chunks"):
            answer = str(state.get("answer") or "")
            yield _sse("token", {"content": answer})
            yield _sse(
                "final",
                {
                    "answer": answer,
                    "game_id": state.get("detected_game_id", game_id or "bg3"),
                    "intent": state.get("intent"),
                    "sources": [],
                    "tool_calls": state.get("tool_calls", []),
                    "trace": state.get("trace", []),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            self._append_successful_turn(session_id=session_id, message=message, answer=answer)
            return

        final_answer = None
        for event in self.answer_generator.stream(
            question=message,
            game_id=state.get("detected_game_id", game_id or "bg3"),
            chunks=state.get("retrieved_chunks") or [],
        ):
            if event["type"] == "token":
                yield _sse("token", {"content": event["content"]})
                continue
            final_answer = event["answer"]

        trace = list(state.get("trace") or [])
        cache_status = final_answer.cache_status if final_answer is not None else "skipped"
        trace.append({"step": "llm_cache", "status": cache_status})
        trace.append(
            {
                "step": "generate_answer",
                "sources": [source.get("title") for source in (final_answer.sources if final_answer else [])],
            }
        )
        answer_text = final_answer.answer if final_answer else ""
        yield _sse(
            "final",
            {
                "answer": answer_text,
                "game_id": state.get("detected_game_id", game_id or "bg3"),
                "intent": state.get("intent"),
                "sources": final_answer.sources if final_answer else [],
                "tool_calls": state.get("tool_calls", []),
                "trace": trace,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        self._append_successful_turn(session_id=session_id, message=message, answer=answer_text)

    def _append_successful_turn(self, *, session_id: str, message: str, answer: str) -> None:
        if not answer:
            return
        self.session_store.append_turn(session_id, "user", message)
        self.session_store.append_turn(session_id, "assistant", answer)


def build_default_chat_service() -> ChatService:
    settings = load_settings()
    entity_registry = load_default_entity_registry(settings.entity_registry_path)
    retriever = build_retriever(
        settings=settings,
        entity_registry=entity_registry,
    )
    llm_provider = _build_llm_provider(settings)
    return ChatService(
        retriever=retriever,
        knowledge_service=KnowledgeService(retriever=retriever, entity_registry=entity_registry),
        mcp_client=_build_mcp_client(settings),
        session_store=InMemorySessionStore(),
        game_detector=_build_game_detector(llm_provider=llm_provider),
        answer_generator=AnswerGenerator(
            llm_provider=llm_provider,
            llm_cache=_build_llm_cache(settings),
            provider_name=settings.llm_provider,
            model_name=settings.llm_model,
        ),
    )


def _build_llm_provider(settings):
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.llm_model)

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter.")
    return OpenRouterProvider(api_key=settings.openrouter_api_key, model=settings.llm_model)


def _build_llm_cache(settings):
    if not settings.llm_cache_enabled:
        return NullLLMCache()
    try:
        return build_redis_llm_cache(
            redis_url=settings.redis_url,
            ttl_seconds=settings.llm_cache_ttl_seconds,
        )
    except Exception as exc:
        logger.warning("LLM cache disabled because Redis cache could not be initialized: %s", exc)
        return NullLLMCache()


def _build_mcp_client(settings):
    if not settings.mcp_enabled:
        return None
    registry = MCPClientRegistry()
    registry.register("bg3", BG3MCPClient(url=settings.bg3_mcp_url))
    registry.register("blue_prince", BluePrinceMCPClient(url=settings.blue_prince_mcp_url))
    return registry


def _build_game_detector(*, llm_provider=None):
    registry = load_tenant_registry("configs/tenants.yaml")
    return GameDetector(
        tenants=[registry.get(game_id) for game_id in registry.game_ids()],
        llm_provider=llm_provider,
        default_game_id="bg3",
    )


def _build_default_game_detector():
    return _build_game_detector(llm_provider=None)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
