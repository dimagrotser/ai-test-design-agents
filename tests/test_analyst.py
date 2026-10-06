import json

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.agents.analyst import analyze
from atda.ports.llm import LLMResponse
from atda.prompts import load_prompt
from atda.schemas.requirements import Gap, Requirement
from atda.schemas.story import AcceptanceCriterion, Story

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="A transaction is checked against the anti-fraud rules.",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
        AcceptanceCriterion(id="AC-2", text="Transactions from KP are rejected."),
    ),
)


def answer(
    requirements: list[dict[str, str]], gaps: list[dict[str, str | None]] | None = None
) -> str:
    return json.dumps({"requirements": requirements, "gaps": gaps or []})


def requirement(ac_id: str, text: str) -> dict[str, str]:
    return {"ac_id": ac_id, "text": text}


TWO = answer(
    [requirement("AC-1", "Amount over 10000 is rejected."), requirement("AC-2", "KP is blocked.")]
)


def test_ids_are_assigned_by_code_in_the_order_of_the_answer() -> None:
    result = analyze(FakeLLMClient([TWO]), STORY)

    assert result.value.requirements == (
        Requirement(id="FRAUD-1.R1", ac_id="AC-1", text="Amount over 10000 is rejected."),
        Requirement(id="FRAUD-1.R2", ac_id="AC-2", text="KP is blocked."),
    )


def test_the_same_answer_gives_the_same_ids_on_every_run() -> None:
    first = analyze(FakeLLMClient([TWO]), STORY)
    second = analyze(FakeLLMClient([TWO]), STORY)

    assert first.value == second.value


def test_one_ac_may_produce_several_requirements() -> None:
    reply = answer(
        [
            requirement("AC-1", "Amount above the limit is rejected."),
            requirement("AC-1", "Amount equal to the limit is handled as stated."),
            requirement("AC-2", "KP is blocked."),
        ]
    )

    result = analyze(FakeLLMClient([reply]), STORY)

    assert [(r.id, r.ac_id) for r in result.value.requirements] == [
        ("FRAUD-1.R1", "AC-1"),
        ("FRAUD-1.R2", "AC-1"),
        ("FRAUD-1.R3", "AC-2"),
    ]


def test_a_requirement_for_an_unknown_ac_is_retried_with_the_known_ids() -> None:
    bad = answer([requirement("AC-9", "Something.")])
    client = FakeLLMClient([bad, TWO])

    result = analyze(client, STORY)

    retry_text = client.requests[1].messages[-1].content
    assert result.attempts == 2
    assert "unknown AC id AC-9" in retry_text
    assert "AC-1, AC-2" in retry_text
    assert len(result.value.requirements) == 2


def test_gaps_may_refer_to_the_story_or_to_an_ac() -> None:
    reply = answer(
        [requirement("AC-1", "Amount over 10000 is rejected.")],
        gaps=[{"ac_id": "AC-1", "text": "Is 10000 allowed?"}, {"ac_id": None, "text": "Currency?"}],
    )

    result = analyze(FakeLLMClient([reply]), STORY)

    assert result.value.gaps == (
        Gap(ac_id="AC-1", text="Is 10000 allowed?"),
        Gap(ac_id=None, text="Currency?"),
    )


def test_a_gap_for_an_unknown_ac_is_retried() -> None:
    bad = answer([requirement("AC-1", "x")], gaps=[{"ac_id": "AC-7", "text": "Unclear."}])
    client = FakeLLMClient([bad, TWO])

    result = analyze(client, STORY)

    assert result.attempts == 2
    assert "unknown AC id AC-7" in client.requests[1].messages[-1].content


@pytest.mark.parametrize(
    "bad",
    [
        answer([]),
        answer([requirement("AC-1", "   ")]),
    ],
    ids=["no requirements", "empty text"],
)
def test_an_empty_analysis_is_retried(bad: str) -> None:
    client = FakeLLMClient([bad, TWO])

    result = analyze(client, STORY)

    assert result.attempts == 2


def test_the_request_carries_the_prompt_the_story_and_the_settings() -> None:
    client = FakeLLMClient([TWO])

    analyze(client, STORY, temperature=0.3, seed=5, num_ctx=8192)

    sent = client.requests[0]
    system, user = sent.messages
    assert system.role == "system"
    assert system.content == load_prompt("requirements_analyst")
    assert user.role == "user"
    for expected in (
        "FRAUD-1",
        "Reject risky transactions",
        "A transaction is checked against the anti-fraud rules.",
        "AC-1: An amount over 10 000 is rejected.",
        "AC-2: Transactions from KP are rejected.",
    ):
        assert expected in user.content
    assert sent.json_schema is not None
    assert (sent.temperature, sent.seed, sent.num_ctx) == (0.3, 5, 8192)


def test_attempts_and_tokens_are_carried_through() -> None:
    bad = LLMResponse(text=answer([]), input_tokens=10, output_tokens=2)
    good = LLMResponse(text=TWO, input_tokens=12, output_tokens=7)

    result = analyze(FakeLLMClient([bad, good]), STORY)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (2, 22, 9)
