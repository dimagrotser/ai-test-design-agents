import json
from collections.abc import Mapping

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.ports.llm import LLMResponse
from atda.refinement import refine_design
from atda.schemas.findings import FindingType, Severity
from atda.schemas.requirements import Analysis, Requirement
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_context import TestContext

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
    gaps=(),
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
# The "mid" class repeats the input of the BVA case above the limit with another outcome.
EP_CONFLICT = {
    "technique": "EP",
    "requirement_id": "FRAUD-1.R1",
    "input_name": "amount",
    "evidence": "over 10 000",
    "classes": [
        {"name": "mid", "values": ["10000.01"], "outcome": APPROVED},
        {"name": "small", "values": ["50"], "outcome": APPROVED},
    ],
}


def designer(*conditions: Mapping[str, object]) -> str:
    return json.dumps({"conditions": list(conditions)})


def critic(*findings: Mapping[str, object]) -> str:
    return json.dumps({"findings": list(findings)})


def issue(
    severity: str = "blocking", message: str = "BVA fits a numeric limit only"
) -> dict[str, str | list[str]]:
    return {
        "type": "wrong_technique",
        "severity": severity,
        "references": ["TC-1"],
        "message": message,
    }


CLEAN_DESIGN = designer(BVA, EP)
CLEAN_REVIEW = critic()


def designer_requests(client: FakeLLMClient) -> list[str]:
    return [r.messages[1].content for r in client.requests if "Target:" in r.messages[1].content]


def test_when_nothing_blocks_the_design_is_reviewed_once_and_not_sent_back() -> None:
    client = FakeLLMClient([CLEAN_DESIGN, critic(issue("warning", "could be nicer"))])

    result = refine_design(client, STORY, ANALYSIS, CONTEXT)

    assert len(client.requests) == 2
    assert [f.message for f in result.value.findings] == ["could be nicer"]
    assert result.value.findings[0].severity is Severity.WARNING


def test_a_blocking_critic_finding_sends_the_design_back_with_its_text_and_the_old_conditions() -> (
    None
):
    client = FakeLLMClient([CLEAN_DESIGN, critic(issue()), designer(BVA, EP), CLEAN_REVIEW])

    result = refine_design(client, STORY, ANALYSIS, CONTEXT)

    assert len(client.requests) == 4
    second_design = designer_requests(client)[1]
    assert "Problems found in your previous answer:" in second_design
    assert "- [wrong_technique] TC-1: BVA fits a numeric limit only" in second_design
    assert '"requirement_id": "FRAUD-1.R1"' in second_design
    assert result.value.findings == ()


def test_a_blocking_deterministic_finding_sends_the_design_back_too() -> None:
    client = FakeLLMClient(
        [designer(BVA, EP_CONFLICT, EP), CLEAN_REVIEW, CLEAN_DESIGN, CLEAN_REVIEW]
    )

    result = refine_design(client, STORY, ANALYSIS, CONTEXT)

    assert len(designer_requests(client)) == 2
    assert "[contradiction]" in designer_requests(client)[1]
    assert result.value.contradictions == ()
    assert result.value.findings == ()


def test_the_loop_stops_after_two_rounds_even_if_blocking_findings_remain() -> None:
    script = [CLEAN_DESIGN, critic(issue())] * 3
    client = FakeLLMClient(script)

    result = refine_design(client, STORY, ANALYSIS, CONTEXT)

    assert len(client.requests) == 6
    assert len(designer_requests(client)) == 3
    assert [f.severity for f in result.value.findings] == [Severity.BLOCKING]
    assert result.value.findings[0].type is FindingType.WRONG_TECHNIQUE


def test_only_blocking_findings_go_back_to_the_designer() -> None:
    review = critic(issue("blocking", "fix this one"), issue("warning", "polish this one"))
    client = FakeLLMClient([CLEAN_DESIGN, review, CLEAN_DESIGN, CLEAN_REVIEW])

    refine_design(client, STORY, ANALYSIS, CONTEXT)

    second_design = designer_requests(client)[1]
    assert "fix this one" in second_design
    assert "polish this one" not in second_design


def test_the_requirements_leave_the_loop_exactly_as_they_came_in() -> None:
    script = [CLEAN_DESIGN, critic(issue())] * 3
    result = refine_design(FakeLLMClient(script), STORY, ANALYSIS, CONTEXT)

    assert result.value.requirements == ANALYSIS.requirements
    assert [r.id for r in result.value.requirements] == ["FRAUD-1.R1", "FRAUD-1.R2"]


def test_zero_rounds_review_once_and_never_go_back() -> None:
    client = FakeLLMClient([CLEAN_DESIGN, critic(issue())])

    result = refine_design(client, STORY, ANALYSIS, CONTEXT, max_rounds=0)

    assert len(client.requests) == 2
    assert [f.severity for f in result.value.findings] == [Severity.BLOCKING]


def test_attempts_and_tokens_add_up_over_the_whole_loop() -> None:
    def answer(text: str, tokens: int) -> LLMResponse:
        return LLMResponse(text=text, input_tokens=tokens, output_tokens=1)

    client = FakeLLMClient(
        [
            answer(CLEAN_DESIGN, 10),
            answer(critic(issue()), 20),
            answer("not json", 5),
            answer(CLEAN_DESIGN, 30),
            answer(CLEAN_REVIEW, 40),
        ]
    )

    result = refine_design(client, STORY, ANALYSIS, CONTEXT)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (5, 105, 5)


@pytest.mark.parametrize("field", ["temperature", "seed", "num_ctx"])
def test_every_request_of_the_loop_uses_the_same_settings(field: str) -> None:
    client = FakeLLMClient([CLEAN_DESIGN, critic(issue()), CLEAN_DESIGN, CLEAN_REVIEW])

    refine_design(client, STORY, ANALYSIS, CONTEXT, temperature=0.3, seed=9, num_ctx=4096)

    assert {getattr(r, field) for r in client.requests} == {
        {"temperature": 0.3, "seed": 9, "num_ctx": 4096}[field]
    }
