import json
from pathlib import Path

import pytest

# Shared scripted answers and the Story of the Variants tests.
from test_variants import CONTEXT, SCRIPTS, SINGLE, STORY

from atda.adapters.anthropic import AnthropicClient
from atda.adapters.fake import FakeLLMClient
from atda.adapters.replay import FixtureStore, MissingFixture, RecordingClient, ReplayClient
from atda.ports.llm import LLMClient, LLMRequest, LLMResponse, Message
from atda.schemas.test_design import TestDesign
from atda.variants import Variant, run_variant

MODEL = "model-x"
KEY = "sk-ant-test-0123456789"


def record(variant: Variant, tmp_path: Path, answers: list[str] | None = None) -> TestDesign:
    inner = FakeLLMClient(answers or SCRIPTS[variant])
    client = RecordingClient(inner, FixtureStore(tmp_path), MODEL)
    return run_variant(variant, client, STORY, CONTEXT).value


def replay(variant: Variant, tmp_path: Path) -> TestDesign:
    client = ReplayClient(FixtureStore(tmp_path), MODEL)
    return run_variant(variant, client, STORY, CONTEXT).value


def request() -> LLMRequest:
    return LLMRequest(messages=(Message(role="user", content="Hi"),), temperature=0.0)


def test_the_recording_client_returns_the_inner_response_and_saves_it(tmp_path: Path) -> None:
    inner = FakeLLMClient([LLMResponse(text="x", input_tokens=3, output_tokens=4)])
    client: LLMClient = RecordingClient(inner, FixtureStore(tmp_path), MODEL)

    response = client.complete(request())

    assert response == LLMResponse(text="x", input_tokens=3, output_tokens=4)
    assert ReplayClient(FixtureStore(tmp_path), MODEL).complete(request()) == response


@pytest.mark.parametrize("variant", list(Variant))
def test_replaying_the_fixtures_reproduces_the_recorded_design_exactly(
    variant: Variant, tmp_path: Path
) -> None:
    recorded = record(variant, tmp_path)

    assert replay(variant, tmp_path) == recorded


def test_one_fixture_is_saved_per_model_call(tmp_path: Path) -> None:
    record(Variant.PIPELINE, tmp_path)

    assert len(list(tmp_path.glob("*.json"))) == 3


def test_a_run_with_a_validation_retry_replays_including_the_retry(tmp_path: Path) -> None:
    recorded = record(Variant.SINGLE_PROMPT, tmp_path, ["not json", SINGLE])

    assert len(list(tmp_path.glob("*.json"))) == 2
    assert replay(Variant.SINGLE_PROMPT, tmp_path) == recorded


def test_replay_of_another_story_fails_with_a_missing_fixture(tmp_path: Path) -> None:
    record(Variant.PIPELINE, tmp_path)
    other = STORY.model_copy(update={"title": "Another title"})
    client = ReplayClient(FixtureStore(tmp_path), MODEL)

    with pytest.raises(MissingFixture):
        run_variant(Variant.PIPELINE, client, other, CONTEXT)


def test_no_key_and_no_header_reach_the_fixture_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    sent: list[dict[str, str]] = []

    def transport(
        url: str, payload: dict[str, object], headers: dict[str, str], *, timeout: float
    ) -> dict[str, object]:
        sent.append(headers)
        return {
            "content": [{"type": "text", "text": SINGLE}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
            "echoed_headers": headers,
        }

    client = RecordingClient(
        AnthropicClient("claude-test", transport=transport), FixtureStore(tmp_path), "claude-test"
    )

    design = run_variant(Variant.SINGLE_PROMPT, client, STORY, CONTEXT).value

    assert sent[0]["x-api-key"] == KEY
    files = list(tmp_path.glob("*.json"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert KEY not in text
        assert "x-api-key" not in text.lower()
        assert "authorization" not in text.lower()
    assert isinstance(design, TestDesign)
    assert json.loads(files[0].read_text(encoding="utf-8"))["response"]["input_tokens"] == 5
