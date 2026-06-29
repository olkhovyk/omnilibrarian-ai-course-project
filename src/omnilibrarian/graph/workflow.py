import warnings

from omnilibrarian.graph.state import AgentState
from omnilibrarian.safety import PromptGuard
from omnilibrarian.tools import ToolRouter
from mcp_servers.bg3.tools import compare_bg3_spells, list_bg3_companions
from mcp_servers.blue_prince.tools import search_puzzle_hint


TOOL_HANDLERS = {
    "compare_bg3_spells": compare_bg3_spells,
    "list_bg3_companions": list_bg3_companions,
    "search_puzzle_hint": search_puzzle_hint,
}


def run_chat_workflow(
    state: AgentState,
    *,
    retriever,
    answer_generator,
    prompt_guard=None,
    knowledge_service=None,
    mcp_client=None,
) -> AgentState:
    workflow = build_chat_workflow(
        retriever=retriever,
        answer_generator=answer_generator,
        prompt_guard=prompt_guard or PromptGuard(),
        knowledge_service=knowledge_service,
        mcp_client=mcp_client,
    )
    return workflow.invoke(state)


def run_context_workflow(
    state: AgentState,
    *,
    retriever,
    prompt_guard=None,
    knowledge_service=None,
    mcp_client=None,
) -> AgentState:
    workflow = build_context_workflow(
        retriever=retriever,
        prompt_guard=prompt_guard or PromptGuard(),
        knowledge_service=knowledge_service,
        mcp_client=mcp_client,
    )
    return workflow.invoke(state)


def build_chat_workflow(*, retriever, answer_generator, prompt_guard=None, knowledge_service=None, mcp_client=None):
    prompt_guard = prompt_guard or PromptGuard()
    try:
        END, StateGraph = _load_langgraph()
    except ImportError as exc:
        return _SequentialWorkflow(
            [
                _prepare_request,
                _safety_guard(prompt_guard),
                _retrieve_or_call_tool(retriever, knowledge_service, mcp_client),
                _generate_answer(answer_generator),
            ],
            missing_dependency=exc,
        )

    graph = StateGraph(AgentState)
    graph.add_node("prepare_request", _prepare_request)
    graph.add_node("safety_guard", _safety_guard(prompt_guard))
    graph.add_node("blocked_response", _blocked_response)
    graph.add_node("retrieve_context", _retrieve_context(retriever))
    graph.add_node("mcp_call", _mcp_call(knowledge_service, mcp_client))
    graph.add_node("generate_answer", _generate_answer(answer_generator))
    graph.set_entry_point("prepare_request")
    graph.add_edge("prepare_request", "safety_guard")
    graph.add_conditional_edges(
        "safety_guard",
        _route_after_safety(knowledge_service),
        {
            "blocked": "blocked_response",
            "rag": "retrieve_context",
            "mcp": "mcp_call",
        },
    )
    graph.add_edge("blocked_response", END)
    graph.add_edge("mcp_call", "generate_answer")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()


def build_context_workflow(*, retriever, prompt_guard=None, knowledge_service=None, mcp_client=None):
    prompt_guard = prompt_guard or PromptGuard()
    try:
        END, StateGraph = _load_langgraph()
    except ImportError as exc:
        return _SequentialWorkflow(
            [
                _prepare_request,
                _safety_guard(prompt_guard),
                _retrieve_or_call_tool(retriever, knowledge_service, mcp_client),
            ],
            missing_dependency=exc,
        )

    graph = StateGraph(AgentState)
    graph.add_node("prepare_request", _prepare_request)
    graph.add_node("safety_guard", _safety_guard(prompt_guard))
    graph.add_node("blocked_response", _blocked_response)
    graph.add_node("retrieve_context", _retrieve_context(retriever))
    graph.add_node("mcp_call", _mcp_call(knowledge_service, mcp_client))
    graph.set_entry_point("prepare_request")
    graph.add_edge("prepare_request", "safety_guard")
    graph.add_conditional_edges(
        "safety_guard",
        _route_after_safety(knowledge_service),
        {
            "blocked": "blocked_response",
            "rag": "retrieve_context",
            "mcp": "mcp_call",
        },
    )
    graph.add_edge("blocked_response", END)
    graph.add_edge("retrieve_context", END)
    graph.add_edge("mcp_call", END)
    return graph.compile()


def _load_langgraph():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
            category=UserWarning,
            module="langchain_core.utils.pydantic",
        )
        from langgraph.graph import END, StateGraph

    return END, StateGraph


class _SequentialWorkflow:
    def __init__(self, nodes, *, missing_dependency: ImportError) -> None:
        self.nodes = nodes
        self.missing_dependency = missing_dependency

    def invoke(self, state: AgentState) -> AgentState:
        current = state
        for node in self.nodes:
            current = node(current)
            if current.get("is_safe") is False:
                current = _blocked_response(current)
                break
        trace = list(current.get("trace") or [])
        trace.append(
            {
                "step": "workflow_runtime",
                "runtime": "sequential_fallback",
                "reason": "langgraph_not_installed",
            }
        )
        return {**current, "trace": trace}


def _prepare_request(state: AgentState) -> AgentState:
    game_id = state.get("game_id") or "bg3"
    memory_context = _build_memory_context(
        query=state.get("original_query", ""),
        history=state.get("history") or [],
    )
    search_query = _build_search_query(
        query=state.get("original_query", ""),
        memory_context=memory_context,
    )
    trace = list(state.get("trace") or [])
    trace_item = {
        "step": "prepare_request",
        "session_id": state.get("session_id"),
        "game_id": game_id,
    }
    if memory_context:
        trace_item["memory_context"] = memory_context
    trace.append(trace_item)
    return {
        **state,
        "detected_game_id": game_id,
        "intent": "rag",
        "memory_context": memory_context,
        "search_query": search_query,
        "trace": trace,
    }


def _safety_guard(prompt_guard):
    def node(state: AgentState) -> AgentState:
        decision = prompt_guard.check(state["original_query"])
        trace = list(state.get("trace") or [])
        if decision.allowed:
            trace.append({"step": "safety_guard", "status": "allowed"})
        else:
            trace.append(
                {
                    "step": "safety_guard",
                    "status": "blocked",
                    "reason": decision.reason,
                }
            )
        return {
            **state,
            "is_safe": decision.allowed,
            "safety_reason": decision.reason,
            "trace": trace,
        }

    return node


def _route_after_safety(knowledge_service):
    def route(state: AgentState) -> str:
        if state.get("is_safe") is False:
            return "blocked"
        if _select_tool(state, knowledge_service) is not None:
            return "mcp"
        return "rag"

    return route


def _blocked_response(state: AgentState) -> AgentState:
    reason = state.get("safety_reason")
    if reason == "secret_exfiltration":
        answer = "Я не можу допомогти з отриманням секретів, API ключів або внутрішніх змінних оточення."
    else:
        answer = "Я не можу допомогти з цим запитом, бо він намагається обійти правила або отримати внутрішні інструкції системи."
    return {
        **state,
        "answer": answer,
        "sources": [],
        "tool_calls": [],
        "retrieved_chunks": [],
    }


def _retrieve_context(retriever):
    def node(state: AgentState) -> AgentState:
        query = state.get("search_query") or state["original_query"]
        game_id = state["detected_game_id"]
        chunks = retriever.search(query, game_id=game_id, limit=5)
        trace = list(state.get("trace") or [])
        trace.append(
            {
                "step": "retrieve_context",
                "retrieval_query": chunks[0].get("retrieval_query") if chunks else query,
                "rewrite_reasons": chunks[0].get("rewrite_reasons") if chunks else [],
                "top_titles": [chunk.get("title") for chunk in chunks],
                "source_mix": _source_mix(chunks),
                "source_policy_reasons": _source_policy_reasons(chunks),
                "top_context": [_trace_context_item(chunk) for chunk in chunks],
            }
        )
        return {
            **state,
            "retrieved_chunks": chunks,
            "retrieval_query": chunks[0].get("retrieval_query") if chunks else query,
            "rewrite_reasons": chunks[0].get("rewrite_reasons") if chunks else [],
            "trace": trace,
        }

    return node


def _trace_context_item(chunk: dict) -> dict:
    return {
        "title": chunk.get("title"),
        "section": chunk.get("section"),
        "source_id": chunk.get("source_id"),
        "retrieval_source": chunk.get("retrieval_source"),
        "retrieval_sources": chunk.get("retrieval_sources") or [],
        "score": chunk.get("score"),
        "rerank_score": chunk.get("rerank_score"),
        "rerank_reasons": chunk.get("rerank_reasons") or [],
        "source_policy_reasons": chunk.get("source_policy_reasons") or [],
    }


def _source_mix(chunks: list[dict]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for chunk in chunks:
        source_id = str(chunk.get("source_id") or "unknown")
        mix[source_id] = mix.get(source_id, 0) + 1
    return mix


def _source_policy_reasons(chunks: list[dict]) -> list[str]:
    reasons: list[str] = []
    for chunk in chunks:
        for reason in chunk.get("source_policy_reasons") or []:
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def _retrieve_or_call_tool(retriever, knowledge_service, mcp_client=None):
    def node(state: AgentState) -> AgentState:
        if _select_tool(state, knowledge_service) is not None:
            return _mcp_call(knowledge_service, mcp_client)(state)
        return _retrieve_context(retriever)(state)

    return node


def _mcp_call(knowledge_service, mcp_client=None):
    def node(state: AgentState) -> AgentState:
        tool_selection = _select_tool(state, knowledge_service)
        if tool_selection is None or knowledge_service is None:
            return _retrieve_context(_NullRetriever())(state)

        tool_name = tool_selection.tool
        arguments = tool_selection.arguments
        if mcp_client is not None:
            result = mcp_client.call_tool(
                game_id=state["detected_game_id"],
                tool_name=tool_name,
                arguments=arguments,
            )
            transport = "mcp_client"
        else:
            result = _call_tool_handler(tool_name, knowledge_service, arguments)
            transport = "local_adapter"
        evidence = result.get("evidence") or []
        trace = list(state.get("trace") or [])
        trace.append(
            {
                "step": "mcp_call",
                "tool": tool_name,
                "status": "ok",
                "transport": transport,
                "arguments": arguments,
            }
        )
        return {
            **state,
            "intent": "mcp_tool",
            "selected_tool": tool_name,
            "tool_result": result,
            "tool_calls": [{"tool": tool_name, "arguments": arguments}],
            "retrieved_chunks": evidence,
            "trace": trace,
        }

    return node


class _NullRetriever:
    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        return []


def _select_tool(state: AgentState, knowledge_service):
    return ToolRouter(knowledge_service).select(
        game_id=state["detected_game_id"],
        query=state.get("search_query") or state["original_query"],
    )


def _call_tool_handler(tool_name: str, knowledge_service, arguments: dict) -> dict:
    handler = TOOL_HANDLERS[tool_name]
    return handler(service=knowledge_service, **arguments)


def _generate_answer(answer_generator):
    def node(state: AgentState) -> AgentState:
        answer = answer_generator.generate(
            question=state["original_query"],
            game_id=state["detected_game_id"],
            chunks=state.get("retrieved_chunks") or [],
        )
        trace = list(state.get("trace") or [])
        trace.append(
            {
                "step": "llm_cache",
                "status": answer.cache_status,
            }
        )
        trace.append(
            {
                "step": "generate_answer",
                "sources": [source.get("title") for source in answer.sources],
            }
        )
        return {
            **state,
            "answer": answer.answer,
            "sources": answer.sources,
            "tool_calls": state.get("tool_calls") or [],
            "trace": trace,
        }

    return node


def _build_memory_context(*, query: str, history: list[dict]) -> str:
    if not history or not _looks_like_follow_up(query):
        return ""

    recent_user_turns = [
        str(turn.get("content") or "").strip()
        for turn in history
        if turn.get("role") == "user" and str(turn.get("content") or "").strip()
    ]
    if not recent_user_turns:
        return ""
    return " | ".join(recent_user_turns[-2:])


def _build_search_query(*, query: str, memory_context: str) -> str:
    if not memory_context:
        return query
    return f"Previous user context: {memory_context}\nFollow-up question: {query}"


def _looks_like_follow_up(query: str) -> bool:
    lowered = query.casefold().strip()
    if not lowered:
        return False
    phrase_markers = (
        "what about",
        "how about",
        "tell me more",
        "and ",
        "also",
        "а ",
        "а що",
        "а яка",
        "а який",
    )
    if any(marker in lowered for marker in phrase_markers):
        return True
    markers = {
        "it",
        "its",
        "this",
        "that",
        "he",
        "she",
        "him",
        "her",
        "they",
        "them",
        "його",
        "її",
        "він",
        "вона",
        "воно",
        "вони",
        "цього",
        "цієї",
        "цей",
        "ця",
    }
    tokens = set(lowered.replace("?", " ").replace(".", " ").replace(",", " ").split())
    return bool(tokens & markers)
