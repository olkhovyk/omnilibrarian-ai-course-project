from dataclasses import dataclass

from omnilibrarian.routing import GameDetector
from omnilibrarian.tenants.models import TenantConfig


TENANTS = [
    TenantConfig(
        game_id="bg3",
        display_name="Baldur's Gate 3",
        description="D&D RPG with companions, spells, classes, and items.",
        mcp_server="bg3",
    ),
    TenantConfig(
        game_id="blue_prince",
        display_name="Blue Prince",
        description="Puzzle game with rooms, blueprints, items, and Room 46.",
        mcp_server="blue_prince",
    ),
]


@dataclass
class FakeLLM:
    response: str
    calls: list[dict] | None = None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls = self.calls or []
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.response

    def stream(self, system_prompt: str, user_prompt: str):
        return iter(())


def test_game_detector_respects_explicit_game_id_without_llm_call():
    llm = FakeLLM('{"game_id":"blue_prince","confidence":1,"reason":"unused"}')
    detector = GameDetector(tenants=TENANTS, llm_provider=llm)

    result = detector.detect(message="What is Room 46?", explicit_game_id="bg3")

    assert result.game_id == "bg3"
    assert result.method == "explicit"
    assert llm.calls is None


def test_game_detector_uses_llm_for_auto_game_id():
    llm = FakeLLM('{"game_id":"blue_prince","confidence":0.91,"reason":"mentions Room 46"}')
    detector = GameDetector(tenants=TENANTS, llm_provider=llm)

    result = detector.detect(message="What is Room 46?", explicit_game_id="auto")

    assert result.game_id == "blue_prince"
    assert result.method == "llm"
    assert result.confidence == 0.91
    assert "Room 46" in llm.calls[0]["user_prompt"]


def test_game_detector_falls_back_to_keywords_when_llm_is_low_confidence():
    llm = FakeLLM('{"game_id":"bg3","confidence":0.1,"reason":"ambiguous"}')
    detector = GameDetector(tenants=TENANTS, llm_provider=llm)

    result = detector.detect(message="How does the Parlor work?", explicit_game_id=None)

    assert result.game_id == "blue_prince"
    assert result.method == "keyword"


def test_game_detector_defaults_when_game_is_ambiguous():
    detector = GameDetector(tenants=TENANTS, llm_provider=None)

    result = detector.detect(message="What should I do next?", explicit_game_id=None)

    assert result.game_id == "bg3"
    assert result.method == "default"


def test_game_detector_rejects_unknown_explicit_game_id_to_default():
    detector = GameDetector(tenants=TENANTS, llm_provider=None)

    result = detector.detect(message="hello", explicit_game_id="unknown")

    assert result.game_id == "bg3"
    assert result.method == "invalid_explicit"
