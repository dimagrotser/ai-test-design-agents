import copy
import json

import pytest

from atda.adapters.anthropic import (
    AnthropicClient,
    IncompleteResponse,
    MissingApiKey,
    strict_schema,
)
from atda.agents.single_prompt import SinglePromptReply
from atda.ports.llm import LLMClient, LLMRequest, Message

KEY = "sk-test-0123456789"
UNSUPPORTED = {"minimum", "maximum", "multipleOf", "minLength", "maxLength", "maxItems", "oneOf"}


class Transport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str], float]] = []

    def __call__(
        self, url: str, payload: dict[str, object], headers: dict[str, str], *, timeout: float
    ) -> dict[str, object]:
        self.calls.append((url, payload, headers, timeout))
        return self.response


def answer(text: str = '{"ok": true}', stop_reason: str = "end_turn") -> dict[str, object]:
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }


def request(**overrides: object) -> LLMRequest:
    fields: dict[str, object] = {
        "messages": (
            Message(role="system", content="Be exact."),
            Message(role="user", content="Story"),
            Message(role="assistant", content="{}"),
            Message(role="user", content="Fix it"),
        ),
        "json_schema": {"type": "object", "properties": {"a": {"type": "integer"}}},
        "temperature": 0.3,
        "seed": 5,
        "num_ctx": 4096,
    }
    return LLMRequest.model_validate(fields | overrides)


@pytest.fixture(autouse=True)
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)


def make(transport: Transport, **kwargs: object) -> AnthropicClient:
    return AnthropicClient("claude-test", transport=transport, **kwargs)  # type: ignore[arg-type]


def walk(node: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            found.extend(walk(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(walk(value))
    return found


def test_the_request_goes_to_the_messages_endpoint_with_the_documented_headers() -> None:
    transport = Transport(answer())

    make(transport).complete(request())

    url, _, headers, _ = transport.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers == {"x-api-key": KEY, "anthropic-version": "2023-06-01"}


def test_the_endpoint_can_be_set() -> None:
    transport = Transport(answer())

    make(transport, endpoint="https://proxy.example.test/v1/messages").complete(request())

    assert transport.calls[0][0] == "https://proxy.example.test/v1/messages"


def test_the_payload_has_the_documented_shape() -> None:
    transport = Transport(answer())

    make(transport, max_tokens=999).complete(request())

    payload = transport.calls[0][1]
    assert payload["model"] == "claude-test"
    assert payload["max_tokens"] == 999
    assert payload["temperature"] == 0.3
    assert payload["system"] == "Be exact."
    assert payload["messages"] == [
        {"role": "user", "content": "Story"},
        {"role": "assistant", "content": "{}"},
        {"role": "user", "content": "Fix it"},
    ]
    assert payload["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {"a": {"type": "integer"}},
                "additionalProperties": False,
            },
        }
    }


def test_seed_and_context_size_are_not_sent() -> None:
    transport = Transport(answer())

    make(transport).complete(request())

    assert set(transport.calls[0][1]) == {
        "model",
        "max_tokens",
        "temperature",
        "system",
        "messages",
        "output_config",
    }


def test_without_a_schema_there_is_no_output_config() -> None:
    transport = Transport(answer())

    make(transport).complete(request(json_schema=None))

    assert "output_config" not in transport.calls[0][1]


def test_without_a_system_message_there_is_no_system_field() -> None:
    transport = Transport(answer())

    make(transport).complete(request(messages=(Message(role="user", content="Hi"),)))

    assert "system" not in transport.calls[0][1]


def test_the_text_and_token_counts_are_mapped_to_the_response() -> None:
    response = make(Transport(answer('{"ok": 1}'))).complete(request())

    assert (response.text, response.input_tokens, response.output_tokens) == ('{"ok": 1}', 11, 7)


def test_several_text_blocks_are_joined() -> None:
    body = answer()
    body["content"] = [{"type": "text", "text": "ab"}, {"type": "text", "text": "cd"}]

    assert make(Transport(body)).complete(request()).text == "abcd"


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_a_cut_off_or_refused_answer_raises_instead_of_reaching_the_retry_loop(
    stop_reason: str,
) -> None:
    with pytest.raises(IncompleteResponse, match=stop_reason):
        make(Transport(answer('{"ok"', stop_reason))).complete(request())


def test_the_client_satisfies_the_port() -> None:
    client: LLMClient = make(Transport(answer()))

    assert client.complete(request()).text


@pytest.mark.parametrize("value", [None, ""])
def test_a_missing_or_empty_key_names_the_variable_and_nothing_else(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)

    with pytest.raises(MissingApiKey, match="ANTHROPIC_API_KEY"):
        make(Transport(answer()))


def test_the_key_variable_name_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("OTHER_KEY", KEY)
    transport = Transport(answer())

    make(transport, key_variable="OTHER_KEY").complete(request())

    assert transport.calls[0][2]["x-api-key"] == KEY


def test_the_key_is_not_in_the_repr_or_in_any_error() -> None:
    client = make(Transport(answer()))

    assert KEY not in repr(client)
    assert KEY not in str(IncompleteResponse("max_tokens"))


def test_additional_properties_is_false_on_every_object() -> None:
    schema = {
        "type": "object",
        "properties": {"inner": {"$ref": "#/$defs/Inner"}},
        "$defs": {"Inner": {"type": "object", "properties": {"x": {"type": "string"}}}},
    }

    result = strict_schema(schema)

    objects = [n for n in walk(result) if n.get("type") == "object"]
    assert len(objects) == 2
    assert all(n["additionalProperties"] is False for n in objects)


def test_keywords_the_api_rejects_are_removed() -> None:
    schema = {
        "type": "object",
        "properties": {
            "n": {"type": "integer", "minimum": 1, "maximum": 3},
            "s": {"type": "string", "minLength": 1, "maxLength": 9},
            "l": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
        },
    }

    result = strict_schema(schema)

    properties = result["properties"]
    assert properties["n"] == {"type": "integer"}  # type: ignore[index]
    assert properties["s"] == {"type": "string"}  # type: ignore[index]
    assert properties["l"] == {"type": "array", "items": {"type": "string"}}  # type: ignore[index]


def test_min_items_of_zero_or_one_is_kept() -> None:
    schema = {"type": "array", "items": {"type": "string"}, "minItems": 1}

    assert strict_schema(schema)["minItems"] == 1


def test_one_of_becomes_any_of_and_the_discriminator_is_dropped() -> None:
    schema = {
        "oneOf": [{"type": "string"}, {"type": "integer"}],
        "discriminator": {"propertyName": "t"},
    }

    assert strict_schema(schema) == {"anyOf": [{"type": "string"}, {"type": "integer"}]}


def test_the_input_schema_is_not_modified() -> None:
    schema = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1}}}
    before = copy.deepcopy(schema)

    strict_schema(schema)

    assert schema == before


def test_the_real_single_prompt_schema_has_nothing_the_api_rejects() -> None:
    result = strict_schema(SinglePromptReply.model_json_schema())

    nodes = walk(result)
    assert not any(UNSUPPORTED & set(n) for n in nodes)
    assert all(n["minItems"] in (0, 1) for n in nodes if "minItems" in n)
    assert all(n["additionalProperties"] is False for n in nodes if n.get("type") == "object")
    json.dumps(result)
