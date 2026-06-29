from __future__ import annotations

from dataclasses import dataclass
import json
import re

from omnilibrarian.llm.base import LLMProvider
from omnilibrarian.tenants.models import TenantConfig


AUTO_GAME_VALUES = {"", "auto", "detect"}


@dataclass(frozen=True)
class GameDetectionResult:
    game_id: str
    method: str
    confidence: float
    reason: str

    def to_trace(self) -> dict[str, object]:
        return {
            "step": "detect_game",
            "game_id": self.game_id,
            "method": self.method,
            "confidence": self.confidence,
            "reason": self.reason,
        }


class GameDetector:
    def __init__(
        self,
        *,
        tenants: list[TenantConfig],
        llm_provider: LLMProvider | None = None,
        default_game_id: str = "bg3",
        min_confidence: float = 0.55,
    ) -> None:
        self.tenants = tenants
        self.llm_provider = llm_provider
        self.default_game_id = default_game_id
        self.min_confidence = min_confidence
        self._known_game_ids = {tenant.game_id for tenant in tenants}

    def detect(self, *, message: str, explicit_game_id: str | None = None) -> GameDetectionResult:
        if explicit_game_id is not None and explicit_game_id.casefold() not in AUTO_GAME_VALUES:
            if explicit_game_id not in self._known_game_ids:
                return GameDetectionResult(
                    game_id=self.default_game_id,
                    method="invalid_explicit",
                    confidence=0.0,
                    reason=f"Unknown explicit game_id: {explicit_game_id}.",
                )
            return GameDetectionResult(
                game_id=explicit_game_id,
                method="explicit",
                confidence=1.0,
                reason="User or UI provided game_id.",
            )

        llm_result = self._detect_with_llm(message)
        if llm_result is not None and llm_result.confidence >= self.min_confidence:
            return llm_result

        fallback = self._detect_with_keywords(message)
        if fallback is not None:
            return fallback

        return GameDetectionResult(
            game_id=self.default_game_id,
            method="default",
            confidence=0.0,
            reason="No reliable game signal found.",
        )

    def _detect_with_llm(self, message: str) -> GameDetectionResult | None:
        if self.llm_provider is None:
            return None

        try:
            raw = self.llm_provider.complete(
                _GAME_DETECTION_SYSTEM_PROMPT,
                _build_game_detection_prompt(message=message, tenants=self.tenants),
            )
            payload = _parse_json_object(raw)
            game_id = str(payload.get("game_id") or "").strip()
            confidence = float(payload.get("confidence") or 0)
            reason = str(payload.get("reason") or "LLM selected tenant.").strip()
        except Exception:
            return None

        if game_id not in self._known_game_ids:
            return None
        return GameDetectionResult(
            game_id=game_id,
            method="llm",
            confidence=max(0.0, min(1.0, confidence)),
            reason=reason,
        )

    def _detect_with_keywords(self, message: str) -> GameDetectionResult | None:
        lowered = message.casefold()
        if _has_any(lowered, BLUE_PRINCE_MARKERS):
            return GameDetectionResult(
                game_id="blue_prince",
                method="keyword",
                confidence=0.7,
                reason="Matched Blue Prince-specific terms.",
            )
        if _has_any(lowered, BG3_MARKERS):
            return GameDetectionResult(
                game_id="bg3",
                method="keyword",
                confidence=0.7,
                reason="Matched Baldur's Gate 3-specific terms.",
            )
        return None


BG3_MARKERS = {
    "baldur",
    "bg3",
    "astarion",
    "shadowheart",
    "fireball",
    "lightning bolt",
    "lae'zel",
    "karlach",
    "gale",
    "wyll",
}

BLUE_PRINCE_MARKERS = {
    "blue prince",
    "room 46",
    "drafting studio",
    "parlor",
    "billiard room",
    "mt. holly",
    "mount holly",
    "blueprints",
    "rooms",
}

_GAME_DETECTION_SYSTEM_PROMPT = (
    "You are a strict classifier for a multi-game RAG assistant. "
    "Return only JSON. Do not answer the user's question."
)


def _build_game_detection_prompt(*, message: str, tenants: list[TenantConfig]) -> str:
    tenant_lines = "\n".join(
        f"- game_id={tenant.game_id}; name={tenant.display_name}; description={tenant.description}"
        for tenant in tenants
    )
    return (
        "Choose which game the user is asking about.\n"
        "If the game is ambiguous, choose the most likely game with low confidence.\n\n"
        f"Known games:\n{tenant_lines}\n\n"
        f"User message:\n{message}\n\n"
        'Return JSON exactly like: {"game_id":"bg3","confidence":0.86,"reason":"short reason"}'
    )


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _has_any(text: str, markers: set[str]) -> bool:
    return any(marker in text for marker in markers)
