import json
from collections.abc import Mapping

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.agents.single_prompt import single_prompt
from atda.ports.llm import LLMResponse
from atda.prompts import load_prompt
from atda.schemas.risk import Priority, Risk
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_context import TestContext

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="A transaction is checked against the anti-fraud rules.",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
        AcceptanceCriterion(id="AC-2", text="Transactions from KP, IR or SY are rejected."),
    ),
)
CONTEXT = TestContext(
    target="fraud.evaluate",
    nominal_input={"amount": "100", "country": "DE"},
    statuses=("approved", "rejected"),
    outcome_keys=("amount_limit", "blocked_country"),
)

APPROVED = {"status": "approved", "outcome_keys": []}
LIMIT = {"status": "rejected", "outcome_keys": ["amount_limit"]}
BLOCKED = {"status": "rejected", "outcome_keys": ["blocked_country"]}

REQUIREMENTS = [
    {"ac_id": "AC-1", "text": "An amount over 10000 is rejected."},
    {"ac_id": "AC-2", "text": "KP, IR and SY are blocked."},
]
GAPS = [{"ac_id": "AC-1", "text": "Is 10000 itself rejected?"}]
BVA = {
    "technique": "BVA",
    "requirement_id": "FRAUD-1.R1",
    "input_name": "amount",
    "evidence": "over 10 000",
    "operator": ">",
    "boundary": "10000",
    "value_type": "decimal",
    "outcome_if_true": LIMIT,
    "outcome_if_false": APPROVED,
}
EP = {
    "technique": "EP",
    "requirement_id": "FRAUD-1.R2",
    "input_name": "country",
    "evidence": "from KP, IR or SY",
    "classes": [
        {"name": "blocked", "values": ["KP", "IR", "SY"], "outcome": BLOCKED},
        {"name": "other", "values": ["DE"], "outcome": APPROVED},
    ],
}
SCORES = [
    {"requirement_id": "FRAUD-1.R1", "likelihood": 3, "impact": 3},
    {"requirement_id": "FRAUD-1.R2", "likelihood": 2, "impact": 2},
]


def reply(**parts: object) -> str:
    whole: dict[str, object] = {
        "requirements": REQUIREMENTS,
        "gaps": GAPS,
        "conditions": [BVA, EP],
        "scores": SCORES,
        **parts,
    }
    return json.dumps(whole)


def changed(base: Mapping[str, object], **updates: object) -> dict[str, object]:
    return {**base, **updates}


GOOD = reply()


def retry_text(client: FakeLLMClient) -> str:
    return client.requests[1].messages[-1].content


def test_one_valid_reply_gives_the_whole_test_design_in_one_call() -> None:
    client = FakeLLMClient([GOOD])

    result = single_prompt(client, STORY, CONTEXT)

    design = result.value
    assert len(client.requests) == 1
    assert result.attempts == 1
    assert [r.id for r in design.requirements] == ["FRAUD-1.R1", "FRAUD-1.R2"]
    assert [r.risk for r in design.requirements] == [
        Risk(likelihood=3, impact=3),
        Risk(likelihood=2, impact=2),
    ]
    assert [g.text for g in design.gaps] == ["Is 10000 itself rejected?"]
    assert len(design.test_cases) == 7
    assert [c.priority for c in design.test_cases[:3]] == [Priority.P1] * 3
    assert {c.priority for c in design.test_cases[3:]} == {Priority.P2}
    assert [c.technique.value for c in design.conditions] == ["BVA", "EP"]


@pytest.mark.parametrize(
    ("bad", "expected"),
    [
        (reply(requirements=[{"ac_id": "AC-9", "text": "x"}]), "unknown AC id AC-9"),
        (reply(requirements=[]), "requirements"),
        (
            reply(conditions=[changed(BVA, evidence="above 10000"), EP]),
            "does not occur in the text of AC-1",
        ),
        (
            reply(
                conditions=[
                    changed(
                        BVA, outcome_if_true={"status": "rejected", "outcome_keys": ["made_up"]}
                    ),
                    EP,
                ]
            ),
            "unknown Outcome Key made_up",
        ),
        (
            reply(
                conditions=[
                    changed(BVA, outcome_if_false={"status": "accepted", "outcome_keys": []}),
                    EP,
                ]
            ),
            "unknown status accepted",
        ),
        (
            reply(conditions=[changed(BVA, requirement_id="FRAUD-1.R3"), EP]),
            "unknown requirement id FRAUD-1.R3",
        ),
        (reply(scores=SCORES[:1]), "no score for FRAUD-1.R2"),
        (reply(scores=[*SCORES, SCORES[0]]), "scored more than once: FRAUD-1.R1"),
        (reply(scores=[changed(SCORES[0], likelihood=4), SCORES[1]]), "likelihood"),
    ],
    ids=[
        "ac",
        "no requirements",
        "evidence",
        "key",
        "status",
        "requirement",
        "missing score",
        "duplicate score",
        "score range",
    ],
)
def test_a_reply_that_breaks_a_rule_is_retried_with_the_error_text(bad: str, expected: str) -> None:
    client = FakeLLMClient([bad, GOOD])

    result = single_prompt(client, STORY, CONTEXT)

    assert result.attempts == 2
    assert expected in retry_text(client)


def test_every_problem_of_a_reply_is_reported_in_one_retry() -> None:
    bad = reply(
        conditions=[changed(BVA, evidence="above 10000"), EP],
        scores=SCORES[:1],
    )
    client = FakeLLMClient([bad, GOOD])

    single_prompt(client, STORY, CONTEXT)

    assert "does not occur in the text of AC-1" in retry_text(client)
    assert "no score for FRAUD-1.R2" in retry_text(client)


def test_the_request_carries_the_prompt_the_story_and_the_test_context() -> None:
    client = FakeLLMClient([GOOD])

    single_prompt(client, STORY, CONTEXT, temperature=0.3, seed=5, num_ctx=8192)

    sent = client.requests[0]
    system, user = sent.messages
    assert system.content == load_prompt("single_prompt")
    for expected in (
        "Story FRAUD-1: Reject risky transactions",
        "AC-1: An amount over 10 000 is rejected.",
        "AC-2: Transactions from KP, IR or SY are rejected.",
        "Target: fraud.evaluate",
        'amount: "100"',
        "Statuses: approved, rejected",
        "Outcome Keys: amount_limit, blocked_country",
    ):
        assert expected in user.content
    assert sent.json_schema is not None
    assert (sent.temperature, sent.seed, sent.num_ctx) == (0.3, 5, 8192)


def test_attempts_and_tokens_are_carried_through() -> None:
    bad = LLMResponse(text="nope", input_tokens=10, output_tokens=2)
    good = LLMResponse(text=GOOD, input_tokens=12, output_tokens=7)

    result = single_prompt(FakeLLMClient([bad, good]), STORY, CONTEXT)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (2, 22, 9)
