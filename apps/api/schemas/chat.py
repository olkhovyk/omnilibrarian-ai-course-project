from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    game_id: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    game_id: str
    intent: str | None = None
    sources: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)
    latency_ms: int
