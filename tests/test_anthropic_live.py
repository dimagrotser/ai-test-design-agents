import json
import os

import pytest

from atda.adapters.anthropic import AnthropicClient
from atda.agents.single_prompt import SinglePromptReply
from atda.ports.llm import LLMRequest, Message

KEY_VARIABLE = "ANTHROPIC_API_KEY"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


# One real call, run by hand: uv run pytest -m live tests/test_anthropic_live.py
@pytest.mark.live
def test_the_api_accepts_our_most_complex_schema_and_returns_json() -> None:
    if not os.environ.get(KEY_VARIABLE):
        pytest.skip(f"{KEY_VARIABLE} is not set; the live test needs a key")
    client = AnthropicClient(os.environ.get("ATDA_LIVE_MODEL", DEFAULT_MODEL), max_tokens=1024)
    request = LLMRequest(
        messages=(
            Message(role="system", content="Reply with JSON that follows the schema."),
            Message(role="user", content="Story S-1, AC-1: an amount over 10 000 is rejected."),
        ),
        json_schema=SinglePromptReply.model_json_schema(),
        temperature=0.0,
    )

    response = client.complete(request)

    assert isinstance(json.loads(response.text), dict)
    assert response.input_tokens > 0
    assert response.output_tokens > 0
