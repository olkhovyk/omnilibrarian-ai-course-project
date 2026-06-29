from typing import TypedDict


class AgentState(TypedDict, total=False):
    original_query: str
    detected_language: str
    search_query: str
    session_id: str
    game_id: str | None
    detected_game_id: str
    intent: str
    is_safe: bool
    safety_reason: str | None
    history: list[dict]
    memory_context: str
    retrieved_chunks: list[dict]
    retrieval_query: str
    rewrite_reasons: list[str]
    selected_tool: str | None
    tool_result: dict | None
    answer: str
    sources: list[dict]
    tool_calls: list[dict]
    trace: list[dict]
