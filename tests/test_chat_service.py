from apps.api.services.chat_service import ChatService
from omnilibrarian.answering import AnswerResult


class FakeRetriever:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        self.calls.append({"query": query, "game_id": game_id, "limit": limit})
        return [
            {
                "title": "Fireball",
                "section": "Lead",
                "source_url": "https://bg3.wiki/wiki/Fireball",
                "retrieval_query": "Fireball damage",
                "rewrite_reasons": ["fireballll->Fireball:fuzzy"],
            }
        ]


class FakeAnswerGenerator:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, *, question: str, game_id: str, chunks: list[dict]) -> AnswerResult:
        self.calls.append({"question": question, "game_id": game_id, "chunks": chunks})
        return AnswerResult(
            answer="Fireball завдає 8d6 шкоди [1].",
            sources=[{"id": 1, "title": "Fireball", "url": "https://bg3.wiki/wiki/Fireball"}],
        )


class FakeSessionStore:
    def __init__(self, history=None) -> None:
        self.history = history or []
        self.appended = []

    def get_history(self, session_id: str) -> list[dict]:
        return self.history

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        self.appended.append({"session_id": session_id, "role": role, "content": content})


def test_chat_service_uses_graph_workflow_response_shape():
    service = ChatService(retriever=FakeRetriever(), answer_generator=FakeAnswerGenerator())

    response = service.answer(message="Яка шкода від fireballll?", session_id="s1", game_id="bg3")

    assert response["answer"] == "Fireball завдає 8d6 шкоди [1]."
    assert response["game_id"] == "bg3"
    assert response["intent"] == "rag"
    assert response["sources"] == [{"id": 1, "title": "Fireball", "url": "https://bg3.wiki/wiki/Fireball"}]
    assert response["tool_calls"] == []
    assert response["trace"][0]["step"] == "detect_game"
    assert response["trace"][0]["method"] == "explicit"
    assert response["trace"][1]["step"] == "prepare_request"
    assert response["trace"][2]["step"] == "safety_guard"
    assert response["trace"][3]["step"] == "retrieve_context"
    assert response["trace"][4]["step"] == "llm_cache"
    assert response["trace"][5]["step"] == "generate_answer"
    assert isinstance(response["latency_ms"], int)


def test_chat_service_reads_and_writes_session_history():
    session_store = FakeSessionStore(history=[{"role": "user", "content": "Tell me about Fireball"}])
    retriever = FakeRetriever()
    service = ChatService(
        retriever=retriever,
        answer_generator=FakeAnswerGenerator(),
        session_store=session_store,
    )

    response = service.answer(message="What about its damage?", session_id="s1", game_id="bg3")

    assert retriever.calls[0]["query"] == (
        "Previous user context: Tell me about Fireball\nFollow-up question: What about its damage?"
    )
    assert response["trace"][1]["memory_context"] == "Tell me about Fireball"
    assert session_store.appended == [
        {"session_id": "s1", "role": "user", "content": "What about its damage?"},
        {"session_id": "s1", "role": "assistant", "content": response["answer"]},
    ]



class FakeKnowledgeService:
    entity_registry = None

    def find_entities(self, *, game_id: str, text: str, content_type: str | None = None) -> list[dict]:
        entities = []
        lowered = text.casefold()
        if "fireball" in lowered:
            entities.append(self.get_entity(game_id=game_id, name="Fireball"))
        if "lightning bolt" in lowered:
            entities.append(self.get_entity(game_id=game_id, name="Lightning Bolt"))
        return entities

    def get_entity(self, *, game_id: str, name: str) -> dict:
        return {
            "game_id": game_id,
            "canonical_name": name,
            "content_type": "spell",
            "source_url": f"https://bg3.wiki/wiki/{name.replace(' ', '_')}",
            "aliases": [],
        }

    def search(self, *, game_id: str, query: str, limit: int = 5) -> list[dict]:
        return [
            {
                "title": "Fireball",
                "section": "Lead",
                "source_url": "https://bg3.wiki/wiki/Fireball",
                "text": "Fireball deals 8d6 Fire damage.",
            }
        ]


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls = []

    def call_tool(self, game_id: str, tool_name: str, arguments: dict) -> dict:
        self.calls.append({"game_id": game_id, "tool_name": tool_name, "arguments": arguments})
        return {
            "game_id": game_id,
            "evidence": [
                {
                    "title": "Fireball",
                    "section": "Lead",
                    "source_url": "https://bg3.wiki/wiki/Fireball",
                    "text": "Fireball deals 8d6 Fire damage.",
                }
            ],
        }


def test_chat_service_returns_mcp_tool_calls_for_tool_routed_requests():
    mcp_client = FakeMCPClient()
    service = ChatService(
        retriever=FakeRetriever(),
        answer_generator=FakeAnswerGenerator(),
        knowledge_service=FakeKnowledgeService(),
        mcp_client=mcp_client,
    )

    response = service.answer(message="Compare Fireball and Lightning Bolt", session_id="s1", game_id="bg3")

    assert response["intent"] == "mcp_tool"
    assert response["tool_calls"] == [
        {
            "tool": "compare_bg3_spells",
            "arguments": {"spell_a": "Fireball", "spell_b": "Lightning Bolt", "limit": 5},
        }
    ]
    assert response["trace"][3]["step"] == "mcp_call"
    assert response["trace"][3]["transport"] == "mcp_client"
    assert mcp_client.calls[0]["tool_name"] == "compare_bg3_spells"


def test_chat_service_can_auto_detect_blue_prince_from_prompt():
    retriever = FakeRetriever()
    answer_generator = FakeAnswerGenerator()
    service = ChatService(retriever=retriever, answer_generator=answer_generator)

    response = service.answer(message="What is Room 46 in Blue Prince?", session_id="s1", game_id="auto")

    assert response["game_id"] == "blue_prince"
    assert response["trace"][0]["step"] == "detect_game"
    assert response["trace"][0]["game_id"] == "blue_prince"
    assert response["trace"][0]["method"] == "keyword"
    assert retriever.calls[0]["game_id"] == "blue_prince"


def test_chat_service_warmup_runs_retriever_once_without_llm_call():
    retriever = FakeRetriever()
    answer_generator = FakeAnswerGenerator()
    service = ChatService(retriever=retriever, answer_generator=answer_generator)

    service.warmup()

    assert retriever.calls == [{"query": "Fireball damage", "game_id": "bg3", "limit": 1}]
    assert answer_generator.calls == []
