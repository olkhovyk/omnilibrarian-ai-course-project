from omnilibrarian.llm.base import LLMProvider


class OpenRouterProvider(LLMProvider):
    def __init__(self, *, api_key: str, model: str, client=None) -> None:
        self.model = model
        self.client = client or self._build_client(api_key)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    def stream(self, system_prompt: str, user_prompt: str):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    def _build_client(self, api_key: str):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenRouterProvider.") from exc
        return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
