from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from apps.api.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/v1/chat", response_model=ChatResponse)
@router.post("/chat", response_model=ChatResponse, include_in_schema=False)
def chat(request: ChatRequest, app_request: Request) -> ChatResponse:
    service = app_request.app.state.chat_service
    if service is None:
        from apps.api.services.chat_service import build_default_chat_service

        service = build_default_chat_service()
        app_request.app.state.chat_service = service

    if request.stream:
        return StreamingResponse(
            service.stream_answer(
                message=request.message,
                session_id=request.session_id,
                game_id=request.game_id,
            ),
            media_type="text/event-stream",
        )

    result = service.answer(
        message=request.message,
        session_id=request.session_id,
        game_id=request.game_id,
    )
    return ChatResponse(**result)
