from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str | None = None


class PromptGuard:
    def check(self, message: str) -> SafetyDecision:
        normalized = message.casefold()
        if _contains_any(
            normalized,
            [
                "system prompt",
                "developer message",
                "ignore previous instructions",
                "ignore all previous instructions",
                "show me your prompt",
                "reveal your prompt",
                "disable safety",
            ],
        ):
            return SafetyDecision(allowed=False, reason="system_prompt_extraction")

        if _contains_any(
            normalized,
            [
                "api key",
                "openrouter_api_key",
                "openai_api_key",
                "print your .env",
                "show .env",
                "reveal secrets",
                "environment variables",
            ],
        ):
            return SafetyDecision(allowed=False, reason="secret_exfiltration")

        return SafetyDecision(allowed=True)


def _contains_any(value: str, patterns: list[str]) -> bool:
    return any(pattern in value for pattern in patterns)
