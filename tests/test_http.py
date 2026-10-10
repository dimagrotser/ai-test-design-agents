import io
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from atda.adapters.http import HttpError, HttpStatusError, HttpTimeout, post_json


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def capture(monkeypatch: pytest.MonkeyPatch, outcome: object) -> list[urllib.request.Request]:
    sent: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeResponse:
        sent.append(request)
        assert timeout == 7.0
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(json.dumps(outcome).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent


def test_post_json_sends_the_payload_and_returns_the_parsed_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = capture(monkeypatch, {"ok": True})

    body = post_json("https://example.test/v1", {"a": 1}, {"x-key": "k"}, timeout=7.0)

    assert body == {"ok": True}
    assert sent[0].full_url == "https://example.test/v1"
    assert sent[0].get_method() == "POST"
    assert json.loads(_data(sent[0])) == {"a": 1}
    assert sent[0].get_header("Content-type") == "application/json"
    assert sent[0].get_header("X-key") == "k"


def test_every_request_carries_the_custom_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = capture(monkeypatch, {})

    post_json("https://example.test/v1", {}, {}, timeout=7.0)

    agent = sent[0].get_header("User-agent")
    assert agent is not None
    assert agent.startswith("atda/")
    assert "Python-urllib" not in agent


def test_a_non_2xx_response_raises_a_status_error_with_the_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = urllib.error.HTTPError(
        "https://example.test/v1", 500, "boom", Message(), io.BytesIO(b'{"error": "overloaded"}')
    )
    capture(monkeypatch, error)

    with pytest.raises(HttpStatusError) as caught:
        post_json("https://example.test/v1", {}, {}, timeout=7.0)

    assert caught.value.status == 500
    assert "overloaded" in str(caught.value)


@pytest.mark.parametrize(
    "timeout_error",
    [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))],
)
def test_a_timeout_raises_a_timeout_error(
    monkeypatch: pytest.MonkeyPatch, timeout_error: BaseException
) -> None:
    capture(monkeypatch, timeout_error)

    with pytest.raises(HttpTimeout):
        post_json("https://example.test/v1", {}, {}, timeout=7.0)


def test_status_and_timeout_errors_are_distinct_http_errors() -> None:
    assert issubclass(HttpStatusError, HttpError)
    assert issubclass(HttpTimeout, HttpError)
    assert not issubclass(HttpStatusError, HttpTimeout)
    assert not issubclass(HttpTimeout, HttpStatusError)


def test_error_messages_do_not_contain_request_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError(
        "https://example.test/v1", 401, "no", Message(), io.BytesIO(b"{}")
    )
    capture(monkeypatch, error)

    with pytest.raises(HttpStatusError) as caught:
        post_json("https://example.test/v1", {}, {"x-api-key": "sk-secret-value"}, timeout=7.0)

    assert "sk-secret-value" not in str(caught.value)


def _data(request: urllib.request.Request) -> Any:  # noqa: ANN401 - urllib types data loosely
    return request.data
