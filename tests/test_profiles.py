import pytest

from atda.adapters.anthropic import AnthropicClient
from atda.adapters.openai_compatible import OpenAICompatibleClient
from atda.adapters.profiles import (
    UnknownProfile,
    available_profiles,
    build_client,
    load_profile,
    profile_from_text,
)
from atda.ports.llm import LLMRequest, Message
from atda.schemas.provider_profile import ProviderProfileError

CLAUDE = "claude-sonnet-5-5"
KEY = "sk-test-0123456789"

PROFILE = """\
adapter: {adapter}
endpoint: https://proxy.example.test/v1/messages
model: model-z
structured_output: {mechanism}
context_size: 1000
timeout: 33
location: cloud
key_variable: PROFILE_TEST_KEY
"""


def text(adapter: str = "anthropic", mechanism: str = "output_config") -> str:
    return PROFILE.format(adapter=adapter, mechanism=mechanism)


def test_the_claude_profile_loads() -> None:
    profile = load_profile(CLAUDE)

    assert profile.adapter == "anthropic"
    assert profile.model == "claude-sonnet-5-5"
    assert profile.endpoint == "https://api.anthropic.com/v1/messages"
    assert profile.structured_output == "output_config"
    assert profile.location == "cloud"
    assert profile.key_variable == "ANTHROPIC_API_KEY"


def test_the_claude_profile_is_listed() -> None:
    assert CLAUDE in available_profiles()


def test_an_unknown_name_fails_and_lists_the_available_names() -> None:
    with pytest.raises(UnknownProfile) as error:
        load_profile("no-such-profile")

    message = str(error.value)
    assert "no-such-profile" in message
    assert all(name in message for name in available_profiles())


@pytest.mark.parametrize("name", ["../etc/passwd", "a/b", "", "claude-sonnet-5-5.yaml"])
def test_a_name_that_is_not_a_listed_profile_never_reaches_the_file_system(name: str) -> None:
    with pytest.raises(UnknownProfile):
        load_profile(name)


def test_an_unknown_adapter_is_rejected() -> None:
    with pytest.raises(ProviderProfileError, match="adapter"):
        profile_from_text(text(adapter="made-up"), "p.yaml")


def test_a_mechanism_the_adapter_does_not_define_is_rejected() -> None:
    with pytest.raises(ProviderProfileError, match="structured_output"):
        profile_from_text(text(mechanism="format"), "p.yaml")


def test_the_client_is_built_from_the_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILE_TEST_KEY", KEY)
    calls: list[tuple[str, dict[str, object], dict[str, str], float]] = []

    def transport(
        url: str, payload: dict[str, object], headers: dict[str, str], *, timeout: float
    ) -> dict[str, object]:
        calls.append((url, payload, headers, timeout))
        return {
            "content": [{"type": "text", "text": "{}"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }

    client = build_client(profile_from_text(text(), "p.yaml"), transport=transport)
    client.complete(LLMRequest(messages=(Message(role="user", content="Hi"),), temperature=0.0))

    assert isinstance(client, AnthropicClient)
    url, payload, headers, timeout = calls[0]
    assert url == "https://proxy.example.test/v1/messages"
    assert payload["model"] == "model-z"
    assert headers["x-api-key"] == KEY
    assert timeout == 33.0


COMPAT = "groq-gpt-oss-120b"


def test_the_openai_compatible_example_profile_loads() -> None:
    profile = load_profile(COMPAT)

    assert profile.adapter == "openai-compatible"
    assert profile.structured_output == "json_schema"
    assert profile.location == "cloud"
    assert profile.key_variable == "GROQ_API_KEY"
    assert profile.endpoint.endswith("/chat/completions")


def test_the_example_profile_is_listed_next_to_the_claude_profile() -> None:
    assert {CLAUDE, COMPAT} <= set(available_profiles())


def test_a_mechanism_of_another_adapter_is_rejected_for_openai_compatible() -> None:
    with pytest.raises(ProviderProfileError, match="structured_output"):
        profile_from_text(text(adapter="openai-compatible", mechanism="output_config"), "p.yaml")


def test_the_openai_compatible_client_is_built_from_its_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROFILE_TEST_KEY", KEY)
    calls: list[tuple[str, dict[str, object], dict[str, str], float]] = []

    def transport(
        url: str, payload: dict[str, object], headers: dict[str, str], *, timeout: float
    ) -> dict[str, object]:
        calls.append((url, payload, headers, timeout))
        return {
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }

    profile = profile_from_text(
        text(adapter="openai-compatible", mechanism="json_schema"), "p.yaml"
    )
    client = build_client(profile, transport=transport)
    client.complete(LLMRequest(messages=(Message(role="user", content="Hi"),), temperature=0.0))

    assert isinstance(client, OpenAICompatibleClient)
    url, payload, headers, timeout = calls[0]
    assert url == "https://proxy.example.test/v1/messages"
    assert payload["model"] == "model-z"
    assert headers == {"Authorization": f"Bearer {KEY}"}
    assert timeout == 33.0
