from omnilibrarian.llm.openai_provider import OpenAIProvider
from omnilibrarian.llm.openrouter_provider import OpenRouterProvider


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)
        self.delta = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return [FakeResponse("Від"), FakeResponse("повідь")]
        return FakeResponse("Відповідь")


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self) -> None:
        self.chat = FakeChat()


def test_openai_provider_sends_system_and_user_messages():
    client = FakeClient()
    provider = OpenAIProvider(api_key="key", model="gpt-test", client=client)

    result = provider.complete("system", "user")

    assert result == "Відповідь"
    call = client.chat.completions.calls[0]
    assert call["model"] == "gpt-test"
    assert call["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]


def test_openrouter_provider_uses_same_chat_completion_contract():
    client = FakeClient()
    provider = OpenRouterProvider(api_key="key", model="openai/gpt-test", client=client)

    result = provider.complete("system", "user")

    assert result == "Відповідь"
    call = client.chat.completions.calls[0]
    assert call["model"] == "openai/gpt-test"


def test_openai_provider_streams_delta_content():
    client = FakeClient()
    provider = OpenAIProvider(api_key="key", model="gpt-test", client=client)

    chunks = list(provider.stream("system", "user"))

    assert chunks == ["Від", "повідь"]
    call = client.chat.completions.calls[0]
    assert call["stream"] is True


def test_openrouter_provider_streams_delta_content():
    client = FakeClient()
    provider = OpenRouterProvider(api_key="key", model="openai/gpt-test", client=client)

    assert list(provider.stream("system", "user")) == ["Від", "повідь"]
