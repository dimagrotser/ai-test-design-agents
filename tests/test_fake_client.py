import pytest

from atda.adapters.fake import FakeLLMClient
from atda.ports.llm import LLMRequest, LLMResponse, Message


def ask(text: str = "hi") -> LLMRequest:
    return LLMRequest(messages=(Message(role="user", content=text),), temperature=0)


def test_scripted_responses_come_back_in_order() -> None:
    client = FakeLLMClient(["one", LLMResponse(text="two", input_tokens=3, output_tokens=4)])

    first = client.complete(ask())
    second = client.complete(ask())

    assert first == LLMResponse(text="one", input_tokens=0, output_tokens=0)
    assert second == LLMResponse(text="two", input_tokens=3, output_tokens=4)


def test_every_request_is_recorded_in_order() -> None:
    client = FakeLLMClient(["a", "b"])

    client.complete(ask("first"))
    client.complete(ask("second"))

    assert [r.messages[0].content for r in client.requests] == ["first", "second"]


def test_running_out_of_responses_is_an_error() -> None:
    client = FakeLLMClient(["only"])
    client.complete(ask())

    with pytest.raises(RuntimeError, match="no scripted response left"):
        client.complete(ask())

    assert len(client.requests) == 2
