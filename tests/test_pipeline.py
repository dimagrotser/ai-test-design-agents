import json

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.pipeline import run_pipeline
from atda.ports.llm import LLMResponse
from atda.prompts import load_prompt
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_context import TestContext
from atda.structured_generation import StructuredGenerationError

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
    ),
)
CONTEXT = TestContext(
    target="fraud.evaluate",
    nominal_input={"amount": "100"},
    statuses=("approved", "rejected"),
    outcome_keys=("amount_limit",),
)

ANALYST = json.dumps(
    {
        "requirements": [{"ac_id": "AC-1", "text": "An amount over 10000 is rejected."}],
        "gaps": [{"ac_id": "AC-1", "text": "Is 10000 itself rejected?"}],
    }
)
DESIGNER = json.dumps(
    {
        "conditions": [
            {
                "technique": "BVA",
                "requirement_id": "FRAUD-1.R1",
                "input_name": "amount",
                "evidence": "over 10 000",
                "operator": ">",
                "boundary": "10000",
                "value_type": "decimal",
                "outcome_if_true": {"status": "rejected", "outcome_keys": ["amount_limit"]},
                "outcome_if_false": {"status": "approved", "outcome_keys": []},
            }
        ]
    }
)


def test_the_designer_works_from_the_requirements_the_analyst_returned() -> None:
    client = FakeLLMClient([ANALYST, DESIGNER])

    result = run_pipeline(client, STORY, CONTEXT)

    design = result.value
    assert [r.id for r in design.requirements] == ["FRAUD-1.R1"]
    assert [g.text for g in design.gaps] == ["Is 10000 itself rejected?"]
    assert [c.overrides["amount"] for c in design.test_cases] == ["9999.99", "10000", "10000.01"]
    assert len(client.requests) == 2
    assert client.requests[0].messages[0].content == load_prompt("requirements_analyst")
    assert client.requests[1].messages[0].content == load_prompt("test_designer")
    assert "FRAUD-1.R1" in client.requests[1].messages[1].content


def test_attempts_and_tokens_add_up_over_both_agents() -> None:
    client = FakeLLMClient(
        [
            LLMResponse(text="not json", input_tokens=5, output_tokens=1),
            LLMResponse(text=ANALYST, input_tokens=6, output_tokens=2),
            LLMResponse(text=DESIGNER, input_tokens=7, output_tokens=3),
        ]
    )

    result = run_pipeline(client, STORY, CONTEXT)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (3, 18, 6)


def test_both_agents_use_the_same_request_settings() -> None:
    client = FakeLLMClient([ANALYST, DESIGNER])

    run_pipeline(client, STORY, CONTEXT, temperature=0.3, seed=9, num_ctx=4096)

    assert [(r.temperature, r.seed, r.num_ctx) for r in client.requests] == [(0.3, 9, 4096)] * 2


def test_when_the_analyst_fails_the_designer_is_never_called() -> None:
    client = FakeLLMClient(["nope", "nope", "nope"])

    with pytest.raises(StructuredGenerationError):
        run_pipeline(client, STORY, CONTEXT)

    assert len(client.requests) == 3
