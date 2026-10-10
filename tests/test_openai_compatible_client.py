import pytest

from atda.adapters.errors import IncompleteResponse, MalformedResponse, MissingApiKey
from atda.adapters.http import HttpStatusError, HttpTimeout
from atda.adapters.openai_compatible import OpenAICompatibleClient
from atda.ports.llm import LLMClient, LLMRequest, Message

KEY = "gsk-test-0123456789"
ENDPOINT = "https://api.example.test/openai/v1/chat/completions"


class Transport:
    def __init__(self, outcome: dict[str, object] | BaseException) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, dict[str, object], dict[str, str], float]] = []

    def __call__(
        self, url: str, payload: dict[str, object], headers: dict[str, str], *, timeout: float
    ) -> dict[str, object]:
        self.calls.append((url, payload, headers, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def answer(text: str = '{"ok": true}', finish_reason: str = "stop") -> dict[str, object]:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


def request(**overrides: object) -> LLMRequest:
    fields: dict[str, object] = {
        "messages": (
            Message(role="system", content="Be exact."),
            Message(role="user", content="Story"),
        ),
        "json_schema": {"type": "object", "properties": {"a": {"type": "integer"}}},
        "temperature": 0.3,
        "seed": 5,
        "num_ctx": 4096,
    }
    return LLMRequest.model_validate(fields | overrides)


@pytest.fixture(autouse=True)
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPAT_API_KEY", KEY)


def make(transport: Transport, **kwargs: object) -> OpenAICompatibleClient:
    options: dict[str, object] = {"endpoint": ENDPOINT, "key_variable": "COMPAT_API_KEY"}
    return OpenAICompatibleClient("model-x", transport=transport, **(options | kwargs))  # type: ignore[arg-type]


def test_the_request_goes_to_the_endpoint_with_a_bearer_token() -> None:
    transport = Transport(answer())

    make(transport, timeout=9.0).complete(request())

    url, _, headers, timeout = transport.calls[0]
    assert url == ENDPOINT
    assert headers == {"Authorization": f"Bearer {KEY}"}
    assert timeout == 9.0


def test_the_payload_has_the_chat_completions_shape() -> None:
    transport = Transport(answer())

    make(transport).complete(request())

    payload = transport.calls[0][1]
    assert payload == {
        "model": "model-x",
        "temperature": 0.3,
        "seed": 5,
        "messages": [
            {"role": "system", "content": "Be exact."},
            {"role": "user", "content": "Story"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "reply",
                "strict": False,
                "schema": {"type": "object", "properties": {"a": {"type": "integer"}}},
            },
        },
    }


def test_without_a_schema_there_is_no_response_format() -> None:
    transport = Transport(answer())

    make(transport).complete(request(json_schema=None))

    assert "response_format" not in transport.calls[0][1]


def test_without_a_seed_there_is_no_seed_field() -> None:
    transport = Transport(answer())

    make(transport).complete(request(seed=None))

    assert "seed" not in transport.calls[0][1]


def test_the_context_size_is_never_sent() -> None:
    transport = Transport(answer())

    make(transport).complete(request())

    assert "num_ctx" not in transport.calls[0][1]


def test_the_text_and_token_counts_are_mapped_to_the_response() -> None:
    response = make(Transport(answer('{"ok": 1}'))).complete(request())

    assert (response.text, response.input_tokens, response.output_tokens) == ('{"ok": 1}', 11, 7)


def test_a_cut_off_answer_raises_instead_of_reaching_the_retry_loop() -> None:
    with pytest.raises(IncompleteResponse, match="length"):
        make(Transport(answer('{"ok"', "length"))).complete(request())


@pytest.mark.parametrize(
    "body",
    [{}, {"choices": []}, {"choices": [{"finish_reason": "stop"}], "usage": {}}, {"usage": {}}],
)
def test_a_body_without_choices_is_malformed(body: dict[str, object]) -> None:
    with pytest.raises(MalformedResponse):
        make(Transport(body)).complete(request())


def test_a_body_without_usage_is_malformed_instead_of_reporting_zero_tokens() -> None:
    body = answer()
    del body["usage"]

    with pytest.raises(MalformedResponse, match="usage"):
        make(Transport(body)).complete(request())


@pytest.mark.parametrize("value", [None, ""])
def test_a_missing_or_empty_key_names_the_variable_and_nothing_else(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("COMPAT_API_KEY")
    else:
        monkeypatch.setenv("COMPAT_API_KEY", value)

    with pytest.raises(MissingApiKey, match="COMPAT_API_KEY"):
        make(Transport(answer()))


def test_the_key_is_not_in_the_repr_or_in_any_error() -> None:
    client = make(Transport(answer()))

    assert KEY not in repr(client)
    for error in (IncompleteResponse("length"), MalformedResponse("no usage")):
        assert KEY not in str(error)


@pytest.mark.parametrize("error", [HttpStatusError(429, "slow down"), HttpTimeout("no answer")])
def test_http_errors_and_timeouts_pass_through_with_their_own_types(error: Exception) -> None:
    with pytest.raises(type(error)):
        make(Transport(error)).complete(request())


def test_the_client_satisfies_the_port() -> None:
    client: LLMClient = make(Transport(answer()))

    assert client.complete(request()).text
