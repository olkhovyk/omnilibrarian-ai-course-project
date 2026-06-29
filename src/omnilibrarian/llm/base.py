from typing import Protocol


class LLMProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...

    def stream(self, system_prompt: str, user_prompt: str):
        ...
