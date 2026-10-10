import json

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.agents.prioritizer import prioritize
from atda.ports.llm import LLMResponse
from atda.prompts import load_prompt
from atda.schemas.requirements import Analysis, Gap, Requirement
from atda.schemas.risk import Risk
from atda.schemas.story import AcceptanceCriterion, Story

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
        AcceptanceCriterion(id="AC-2", text="Transactions from KP, IR or SY are rejected."),
    ),
)
ANALYSIS = Analysis(
    requirements=(
        Requirement(id="FRAUD-1.R1", ac_id="AC-1", text="An amount over 10000 is rejected."),
        Requirement(id="FRAUD-1.R2", ac_id="AC-2", text="KP, IR and SY are blocked."),
    ),
    gaps=(Gap(ac_id="AC-1", text="Is 10000 itself rejected?"), Gap(text="Which currency?")),
)


def score(requirement_id: str, likelihood: object, impact: object) -> dict[str, object]:
    return {"requirement_id": requirement_id, "likelihood": likelihood, "impact": impact}


def reply(*scores: dict[str, object]) -> str:
    return json.dumps({"scores": list(scores)})


GOOD = reply(score("FRAUD-1.R1", 3, 3), score("FRAUD-1.R2", 2, 1))


def retry_text(client: FakeLLMClient) -> str:
    return client.requests[1].messages[-1].content


def test_every_requirement_gets_its_risk_and_nothing_else_changes() -> None:
    result = prioritize(FakeLLMClient([GOOD]), STORY, ANALYSIS)

    rated = result.value.requirements
    assert [r.risk for r in rated] == [Risk(likelihood=3, impact=3), Risk(likelihood=2, impact=1)]
    assert [(r.id, r.ac_id, r.text) for r in rated] == [
        (r.id, r.ac_id, r.text) for r in ANALYSIS.requirements
    ]
    assert result.value.gaps == ANALYSIS.gaps


@pytest.mark.parametrize(
    ("bad", "expected"),
    [(0, "greater than or equal to 1"), (4, "less than or equal to 3"), ("high", "valid integer")],
)
def test_a_score_outside_one_to_three_is_retried_with_the_error_text(
    bad: object, expected: str
) -> None:
    client = FakeLLMClient([reply(score("FRAUD-1.R1", bad, 3), score("FRAUD-1.R2", 2, 1)), GOOD])

    result = prioritize(client, STORY, ANALYSIS)

    assert result.attempts == 2
    assert "likelihood" in retry_text(client)
    assert expected in retry_text(client)


def test_a_requirement_without_a_score_is_retried() -> None:
    client = FakeLLMClient([reply(score("FRAUD-1.R1", 3, 3)), GOOD])

    prioritize(client, STORY, ANALYSIS)

    assert "no score for FRAUD-1.R2" in retry_text(client)


def test_an_unknown_requirement_id_is_retried_with_the_known_ones() -> None:
    bad = reply(score("FRAUD-1.R1", 1, 1), score("FRAUD-1.R2", 1, 1), score("FRAUD-1.R9", 1, 1))
    client = FakeLLMClient([bad, GOOD])

    prioritize(client, STORY, ANALYSIS)

    assert "unknown requirement id FRAUD-1.R9" in retry_text(client)
    assert "known ids: FRAUD-1.R1, FRAUD-1.R2" in retry_text(client)


def test_a_requirement_scored_twice_is_retried() -> None:
    bad = reply(score("FRAUD-1.R1", 1, 1), score("FRAUD-1.R1", 2, 2), score("FRAUD-1.R2", 1, 1))
    client = FakeLLMClient([bad, GOOD])

    prioritize(client, STORY, ANALYSIS)

    assert "scored more than once: FRAUD-1.R1" in retry_text(client)


def test_every_problem_of_an_answer_is_reported_in_one_retry() -> None:
    bad = reply(score("FRAUD-1.R1", 1, 1), score("FRAUD-1.R1", 2, 2), score("FRAUD-1.R9", 1, 1))
    client = FakeLLMClient([bad, GOOD])

    prioritize(client, STORY, ANALYSIS)

    text = retry_text(client)
    assert "unknown requirement id FRAUD-1.R9" in text
    assert "scored more than once: FRAUD-1.R1" in text
    assert "no score for FRAUD-1.R2" in text


def test_an_answer_without_scores_is_retried() -> None:
    client = FakeLLMClient([reply(), GOOD])

    assert prioritize(client, STORY, ANALYSIS).attempts == 2


def test_the_request_carries_the_prompt_the_requirements_and_the_gaps() -> None:
    client = FakeLLMClient([GOOD])

    prioritize(client, STORY, ANALYSIS, temperature=0.3, seed=5, num_ctx=8192)

    sent = client.requests[0]
    system, user = sent.messages
    assert system.content == load_prompt("risk_prioritizer")
    for expected in (
        "FRAUD-1.R1",
        "AC-1: An amount over 10 000 is rejected.",
        "An amount over 10000 is rejected.",
        "FRAUD-1.R2",
        "AC-2: Transactions from KP, IR or SY are rejected.",
        "AC-1: Is 10000 itself rejected?",
        "Story: Which currency?",
    ):
        assert expected in user.content
    assert sent.json_schema is not None
    assert (sent.temperature, sent.seed, sent.num_ctx) == (0.3, 5, 8192)


def test_a_story_without_gaps_says_so() -> None:
    client = FakeLLMClient([GOOD])

    prioritize(
        client,
        STORY,
        Analysis(requirements=ANALYSIS.requirements, gaps=()),
    )

    assert "Gaps: none" in client.requests[0].messages[1].content


def test_attempts_and_tokens_are_carried_through() -> None:
    bad = LLMResponse(text=reply(), input_tokens=10, output_tokens=2)
    good = LLMResponse(text=GOOD, input_tokens=12, output_tokens=7)

    result = prioritize(FakeLLMClient([bad, good]), STORY, ANALYSIS)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (2, 22, 9)
