import json
from collections.abc import Mapping

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.agents.designer import design_tests
from atda.ports.llm import LLMResponse
from atda.prompts import load_prompt
from atda.schemas.requirements import Analysis, Gap, Requirement
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
ANALYSIS = Analysis(
    requirements=(
        Requirement(id="FRAUD-1.R1", ac_id="AC-1", text="An amount over 10000 is rejected."),
        Requirement(id="FRAUD-1.R2", ac_id="AC-2", text="KP, IR and SY are blocked."),
    ),
    gaps=(Gap(ac_id="AC-1", text="Is 10000 itself rejected?"), Gap(text="Which currency?")),
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
OTHER_CLASS = {"name": "other", "values": ["DE"], "outcome": APPROVED}
EP = {
    "technique": "EP",
    "requirement_id": "FRAUD-1.R2",
    "input_name": "country",
    "evidence": "from KP, IR or SY",
    "classes": [{"name": "blocked", "values": ["KP", "IR", "SY"], "outcome": BLOCKED}, OTHER_CLASS],
}


def reply(*conditions: Mapping[str, object]) -> str:
    return json.dumps({"conditions": list(conditions)})


def changed(base: Mapping[str, object], **updates: object) -> dict[str, object]:
    return {**base, **updates}


def retry_text(client: FakeLLMClient) -> str:
    return client.requests[1].messages[-1].content


def test_a_valid_answer_is_expanded_into_test_cases_with_their_traces() -> None:
    result = design_tests(FakeLLMClient([reply(BVA, EP)]), STORY, ANALYSIS, CONTEXT)

    cases = result.value.test_cases
    assert [c.id for c in cases] == [f"TC-{n}" for n in range(1, 8)]
    assert [c.overrides for c in cases[:3]] == [
        {"amount": "9999.99"},
        {"amount": "10000"},
        {"amount": "10000.01"},
    ]
    assert cases[2].expected.outcome_keys == ("amount_limit",)
    assert (cases[0].requirement_ids, cases[0].ac_ids) == (("FRAUD-1.R1",), ("AC-1",))
    assert (cases[3].requirement_ids, cases[3].ac_ids) == (("FRAUD-1.R2",), ("AC-2",))
    assert [c.overrides["country"] for c in cases[3:]] == ["KP", "IR", "SY", "DE"]


def test_the_analysts_requirements_and_gaps_are_carried_over_unchanged() -> None:
    result = design_tests(FakeLLMClient([reply(BVA)]), STORY, ANALYSIS, CONTEXT)

    assert result.value.story_id == "FRAUD-1"
    assert result.value.requirements == ANALYSIS.requirements
    assert result.value.gaps == ANALYSIS.gaps


def test_evidence_that_is_not_in_the_ac_text_is_retried_and_named() -> None:
    client = FakeLLMClient([reply(changed(BVA, evidence="above 10000")), reply(BVA)])

    result = design_tests(client, STORY, ANALYSIS, CONTEXT)

    assert result.attempts == 2
    assert "condition 1 (BVA on amount)" in retry_text(client)
    assert "'above 10000'" in retry_text(client)
    assert "AC-1" in retry_text(client)


def test_evidence_may_differ_from_the_ac_text_in_whitespace() -> None:
    client = FakeLLMClient([reply(changed(BVA, evidence="over   10 000"))])

    assert design_tests(client, STORY, ANALYSIS, CONTEXT).attempts == 1


def test_evidence_is_case_sensitive() -> None:
    client = FakeLLMClient([reply(changed(BVA, evidence="OVER 10 000")), reply(BVA)])

    assert design_tests(client, STORY, ANALYSIS, CONTEXT).attempts == 2


def test_an_outcome_key_outside_the_test_context_is_retried_with_the_known_keys() -> None:
    made_up = {"status": "rejected", "outcome_keys": ["made_up"]}
    client = FakeLLMClient([reply(changed(BVA, outcome_if_true=made_up)), reply(BVA)])

    design_tests(client, STORY, ANALYSIS, CONTEXT)

    assert "unknown Outcome Key made_up" in retry_text(client)
    assert "known keys: amount_limit, blocked_country" in retry_text(client)


def test_an_unknown_outcome_key_in_an_ep_class_is_retried() -> None:
    made_up = {"status": "rejected", "outcome_keys": ["made_up"]}
    classes = [{"name": "blocked", "values": ["KP"], "outcome": made_up}, OTHER_CLASS]
    client = FakeLLMClient([reply(changed(EP, classes=classes)), reply(EP)])

    design_tests(client, STORY, ANALYSIS, CONTEXT)

    assert "class blocked" in retry_text(client)
    assert "unknown Outcome Key made_up" in retry_text(client)


@pytest.mark.parametrize(
    ("bad", "expected"),
    [
        (changed(BVA, requirement_id="FRAUD-1.R9"), "unknown requirement id FRAUD-1.R9"),
        (changed(BVA, input_name="region"), "input region is not in the Nominal Input"),
        (
            changed(BVA, outcome_if_false={"status": "accepted", "outcome_keys": []}),
            "unknown status accepted",
        ),
    ],
    ids=["requirement", "input", "status"],
)
def test_other_unknown_names_are_retried_with_what_is_known(
    bad: Mapping[str, object], expected: str
) -> None:
    client = FakeLLMClient([reply(bad), reply(BVA)])

    design_tests(client, STORY, ANALYSIS, CONTEXT)

    assert expected in retry_text(client)


def test_an_answer_without_conditions_is_retried() -> None:
    client = FakeLLMClient([reply(), reply(BVA)])

    assert design_tests(client, STORY, ANALYSIS, CONTEXT).attempts == 2


def test_every_problem_of_an_answer_is_reported_in_one_retry() -> None:
    bad = changed(BVA, evidence="above 10000", input_name="region")
    worse = changed(EP, requirement_id="FRAUD-1.R9")
    client = FakeLLMClient([reply(bad, worse), reply(BVA)])

    design_tests(client, STORY, ANALYSIS, CONTEXT)

    text = retry_text(client)
    assert "condition 1 (BVA on region)" in text
    assert "evidence 'above 10000'" in text
    assert "input region is not in the Nominal Input" in text
    assert "condition 2 (EP on country)" in text
    assert "unknown requirement id FRAUD-1.R9" in text


def test_the_request_carries_the_prompt_the_requirements_and_the_target() -> None:
    client = FakeLLMClient([reply(BVA)])

    design_tests(client, STORY, ANALYSIS, CONTEXT, temperature=0.3, seed=5, num_ctx=8192)

    sent = client.requests[0]
    system, user = sent.messages
    assert system.content == load_prompt("test_designer")
    for expected in (
        "FRAUD-1.R1",
        "AC-1: An amount over 10 000 is rejected.",
        "FRAUD-1.R2",
        "AC-2: Transactions from KP, IR or SY are rejected.",
        "fraud.evaluate",
        'amount: "100"',
        'country: "DE"',
        "approved, rejected",
        "amount_limit, blocked_country",
    ):
        assert expected in user.content
    assert sent.json_schema is not None
    assert (sent.temperature, sent.seed, sent.num_ctx) == (0.3, 5, 8192)


def test_attempts_and_tokens_are_carried_through() -> None:
    bad = LLMResponse(text=reply(), input_tokens=10, output_tokens=2)
    good = LLMResponse(text=reply(BVA), input_tokens=12, output_tokens=7)

    result = design_tests(FakeLLMClient([bad, good]), STORY, ANALYSIS, CONTEXT)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (2, 22, 9)
