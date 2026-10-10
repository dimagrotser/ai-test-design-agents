import json

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.agents.critic import critique
from atda.ports.llm import LLMResponse
from atda.prompts import load_prompt
from atda.report import render_markdown
from atda.schemas.findings import Finding, FindingType, Severity
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_condition import Technique
from atda.schemas.test_design import TestCase, TestDesign

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
    ),
)
DESIGN = TestDesign(
    story_id="FRAUD-1",
    requirements=(Requirement(id="FRAUD-1.R1", ac_id="AC-1", text="Over the limit is rejected."),),
    gaps=(),
    test_cases=(
        TestCase(
            id="TC-1",
            requirement_ids=("FRAUD-1.R1",),
            ac_ids=("AC-1",),
            technique=Technique.BVA,
            rationale="boundary",
            overrides={"amount": "10000.01"},
            expected=ExpectedOutcome(status="rejected", outcome_keys=()),
        ),
    ),
)


def finding(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "type": "wrong_technique",
        "severity": "blocking",
        "references": ["TC-1"],
        "message": "BVA does not fit a set of countries.",
    }
    return {**base, **fields}


def reply(*findings: dict[str, object]) -> str:
    return json.dumps({"findings": list(findings)})


def retry_text(client: FakeLLMClient) -> str:
    return client.requests[1].messages[-1].content


def test_a_valid_reply_gives_typed_findings() -> None:
    answer = reply(
        finding(),
        finding(type="vague_expected_result", severity="warning", references=["FRAUD-1.R1"]),
    )

    result = critique(FakeLLMClient([answer]), STORY, DESIGN)

    assert result.value.findings == (
        Finding(
            type=FindingType.WRONG_TECHNIQUE,
            severity=Severity.BLOCKING,
            references=("TC-1",),
            message="BVA does not fit a set of countries.",
        ),
        Finding(
            type=FindingType.VAGUE_EXPECTED_RESULT,
            severity=Severity.WARNING,
            references=("FRAUD-1.R1",),
            message="BVA does not fit a set of countries.",
        ),
    )


def test_a_design_with_nothing_to_report_gives_an_empty_reply() -> None:
    assert critique(FakeLLMClient([reply()]), STORY, DESIGN).value.findings == ()


@pytest.mark.parametrize(
    ("bad", "expected"),
    [
        (finding(type="contradiction"), "type must be wrong_technique or vague_expected_result"),
        (finding(type="nonsense"), "type"),
        (finding(severity="critical"), "'blocking' or 'warning'"),
        (finding(references=["TC-99"]), "unknown reference TC-99; known ids: TC-1, FRAUD-1.R1"),
        (finding(references=[]), "no reference"),
    ],
    ids=["deterministic type", "unknown type", "severity", "reference", "no reference"],
)
def test_an_unusable_finding_is_retried_with_the_error_text(
    bad: dict[str, object], expected: str
) -> None:
    client = FakeLLMClient([reply(bad), reply(finding())])

    result = critique(client, STORY, DESIGN)

    assert result.attempts == 2
    assert expected in retry_text(client)


def test_the_request_carries_the_prompt_and_the_report_a_human_would_read() -> None:
    client = FakeLLMClient([reply()])

    critique(client, STORY, DESIGN, temperature=0.3, seed=5, num_ctx=8192)

    sent = client.requests[0]
    system, user = sent.messages
    assert system.content == load_prompt("critic")
    assert user.content == render_markdown(STORY, DESIGN)
    assert sent.json_schema is not None
    assert (sent.temperature, sent.seed, sent.num_ctx) == (0.3, 5, 8192)


def test_attempts_and_tokens_are_carried_through() -> None:
    bad = LLMResponse(text="nope", input_tokens=10, output_tokens=2)
    good = LLMResponse(text=reply(), input_tokens=12, output_tokens=7)

    result = critique(FakeLLMClient([bad, good]), STORY, DESIGN)

    assert (result.attempts, result.input_tokens, result.output_tokens) == (2, 22, 9)
