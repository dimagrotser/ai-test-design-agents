from decimal import Decimal

import pytest

from atda.findings import deterministic_findings
from atda.lexicon import Lexicon, load_lexicon
from atda.schemas.findings import SEMANTIC_TYPES, Finding, FindingType, Severity, finding
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.scalar import Scalar
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_condition import (
    BvaCondition,
    EpCondition,
    EquivalenceClass,
    Operator,
    Technique,
)
from atda.schemas.test_design import Contradiction, TestCase, TestDesign


def test_a_contradiction_is_blocking() -> None:
    found = finding(FindingType.CONTRADICTION, ("TC-1", "TC-2"), "same input, different outcome")

    assert found.severity is Severity.BLOCKING
    assert found.references == ("TC-1", "TC-2")


@pytest.mark.parametrize(
    "type_",
    [
        FindingType.MISSING_COVERAGE,
        FindingType.UNTRACEABLE,
        FindingType.DUPLICATE,
        FindingType.OPERATOR_MISMATCH,
    ],
)
def test_every_other_type_only_warns(type_: FindingType) -> None:
    assert finding(type_, ("X-1",), "message").severity is Severity.WARNING


@pytest.mark.parametrize("type_", [FindingType.WRONG_TECHNIQUE, FindingType.VAGUE_EXPECTED_RESULT])
def test_the_semantic_types_are_set_by_the_critic_and_not_by_the_deterministic_helper(
    type_: FindingType,
) -> None:
    assert type_ in SEMANTIC_TYPES
    with pytest.raises(ValueError, match="semantic"):
        finding(type_, ("TC-1",), "message")


def test_a_finding_survives_a_json_round_trip() -> None:
    found = finding(FindingType.MISSING_COVERAGE, ("AC-3",), "AC-3 has no Test Case")

    assert Finding.model_validate_json(found.model_dump_json()) == found


STORY = Story(
    id="S-1",
    title="T",
    text="",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
        AcceptanceCriterion(id="AC-2", text="KP is blocked."),
    ),
)
NOMINAL: dict[str, Scalar] = {"amount": "100", "country": "DE"}
APPROVED = ExpectedOutcome(status="approved", outcome_keys=())
REJECTED = ExpectedOutcome(status="rejected", outcome_keys=("amount_limit",))


def case(
    case_id: str,
    overrides: dict[str, Scalar],
    expected: ExpectedOutcome = REJECTED,
    requirements: tuple[str, ...] = ("S-1.R1",),
    acs: tuple[str, ...] = ("AC-1",),
) -> TestCase:
    return TestCase(
        id=case_id,
        requirement_ids=requirements,
        ac_ids=acs,
        technique=Technique.BVA,
        rationale="why",
        overrides=overrides,
        expected=expected,
    )


def bva(evidence: str, operator: Operator, requirement: str = "S-1.R1") -> BvaCondition:
    return BvaCondition(
        requirement_id=requirement,
        input_name="amount",
        evidence=evidence,
        operator=operator,
        boundary=Decimal(10000),
        value_type="decimal",
        outcome_if_true=REJECTED,
        outcome_if_false=APPROVED,
    )


def design(**changes: object) -> TestDesign:
    base: dict[str, object] = {
        "story_id": "S-1",
        "requirements": (
            Requirement(id="S-1.R1", ac_id="AC-1", text="x"),
            Requirement(id="S-1.R2", ac_id="AC-2", text="y"),
        ),
        "gaps": (),
        "test_cases": (
            case("TC-1", {"amount": "10000.01"}),
            case("TC-2", {"country": "KP"}, REJECTED, ("S-1.R2",), ("AC-2",)),
        ),
    }
    return TestDesign.model_validate({**base, **changes})


def findings(candidate: TestDesign, lexicon: Lexicon | None = None) -> tuple[Finding, ...]:
    return deterministic_findings(STORY, candidate, NOMINAL, lexicon or load_lexicon())


def kinds(found: tuple[Finding, ...]) -> list[FindingType]:
    return [f.type for f in found]


def test_a_clean_design_has_no_findings() -> None:
    assert findings(design()) == ()


def test_an_ac_without_a_requirement_or_without_a_test_case_is_missing_coverage() -> None:
    story = Story(
        id="S-1",
        title="T",
        text="",
        acceptance_criteria=(
            *STORY.acceptance_criteria,
            AcceptanceCriterion(id="AC-3", text="No requirement."),
        ),
    )
    only_first = design(test_cases=(case("TC-1", {"amount": "10000.01"}),))

    found = deterministic_findings(story, only_first, NOMINAL, load_lexicon())

    assert [(f.type, f.references, f.message) for f in found] == [
        (FindingType.MISSING_COVERAGE, ("AC-2",), "AC-2 has no Test Case"),
        (FindingType.MISSING_COVERAGE, ("AC-3",), "AC-3 has no Requirement and no Test Case"),
        (FindingType.MISSING_COVERAGE, ("S-1.R2",), "S-1.R2 has no Test Case"),
    ]


@pytest.mark.parametrize(
    ("bad", "problem"),
    [
        (case("TC-9", {}, requirements=()), "no Requirement"),
        (case("TC-9", {}, acs=()), "no AC"),
        (case("TC-9", {}, requirements=("S-1.R7",)), "unknown Requirement S-1.R7"),
        (case("TC-9", {}, acs=("AC-9",)), "unknown AC AC-9"),
    ],
)
def test_a_test_case_that_cannot_be_traced_is_reported(bad: TestCase, problem: str) -> None:
    good = design().test_cases
    candidate = design(test_cases=(*good, bad))

    untraceable = [f for f in findings(candidate) if f.type is FindingType.UNTRACEABLE]

    assert len(untraceable) == 1
    assert untraceable[0].references == ("TC-9",)
    assert problem in untraceable[0].message


@pytest.mark.parametrize(
    "second",
    [
        case("TC-3", {"amount": "10000.01"}),
        case("TC-3", {"amount": "10000.010"}),
        case("TC-3", {"amount": 10000.01}),
    ],
)
def test_two_cases_with_the_same_input_and_outcome_are_a_duplicate(second: TestCase) -> None:
    candidate = design(test_cases=(*design().test_cases, second))

    duplicates = [f for f in findings(candidate) if f.type is FindingType.DUPLICATE]

    assert [d.references for d in duplicates] == [("TC-1", "TC-3")]


def test_an_override_equal_to_the_nominal_value_repeats_a_case_without_overrides() -> None:
    cases = (case("TC-1", {}, APPROVED), case("TC-2", {"country": "DE"}, APPROVED))

    duplicates = [f for f in findings(design(test_cases=cases)) if f.type is FindingType.DUPLICATE]

    assert [d.references for d in duplicates] == [("TC-1", "TC-2")]


def test_the_same_input_with_different_outcomes_or_different_inputs_is_no_duplicate() -> None:
    cases = (
        case("TC-1", {"amount": "5"}, REJECTED),
        case("TC-2", {"amount": "5"}, APPROVED),
        case("TC-3", {"amount": "6"}, REJECTED),
    )

    assert FindingType.DUPLICATE not in kinds(findings(design(test_cases=cases)))


def test_each_contradiction_of_the_design_is_a_blocking_finding() -> None:
    candidate = design(
        contradictions=(
            Contradiction(case_ids=("TC-1", "TC-2")),
            Contradiction(case_ids=("TC-3", "TC-4")),
        )
    )

    found = [f for f in findings(candidate) if f.type is FindingType.CONTRADICTION]

    assert [(f.references, f.severity) for f in found] == [
        (("TC-1", "TC-2"), Severity.BLOCKING),
        (("TC-3", "TC-4"), Severity.BLOCKING),
    ]
    assert not [f for f in findings(design()) if f.type is FindingType.CONTRADICTION]


@pytest.mark.parametrize(
    ("evidence", "operator", "warns"),
    [
        ("over 10 000", Operator.GT, False),
        ("over 10 000", Operator.GE, True),
        ("exceeds 10 000", Operator.GT, False),
        ("at least 10 000", Operator.GE, False),
        ("at least 10 000", Operator.GT, True),
        ("10 000 or more", Operator.GE, False),
        ("no more than 10 000", Operator.LE, False),
        ("no more than 10 000", Operator.GT, True),
        ("up to 10 000", Operator.LE, False),
        ("fewer than 10 000", Operator.LT, False),
        ("exactly 10 000", Operator.EQ, False),
        ("at least 10 000 and no more than 20 000", Operator.GE, False),
        ("at least 10 000 and no more than 20 000", Operator.LE, False),
        ("at least 10 000 and no more than 20 000", Operator.GT, True),
        ("a limit of 10 000", Operator.GT, False),
    ],
)
def test_a_bva_operator_that_disagrees_with_the_wording_of_its_evidence_warns(
    evidence: str, operator: Operator, warns: bool
) -> None:
    candidate = design(conditions=(bva(evidence, operator),))

    found = [f for f in findings(candidate) if f.type is FindingType.OPERATOR_MISMATCH]

    assert bool(found) is warns
    if warns:
        assert found[0].severity is Severity.WARNING
        assert found[0].references == ("S-1.R1",)
        assert repr(evidence) in found[0].message
        assert f"the condition uses {operator.value}" in found[0].message


def test_only_bva_conditions_are_checked_for_their_operator() -> None:
    ep = EpCondition(
        requirement_id="S-1.R2",
        input_name="country",
        evidence="over the border",
        classes=(
            EquivalenceClass(name="a", values=("KP",), outcome=REJECTED),
            EquivalenceClass(name="b", values=("DE",), outcome=APPROVED),
        ),
    )

    assert findings(design(conditions=(ep,))) == ()


def test_a_phrase_added_to_the_lexicon_is_used_without_a_code_change() -> None:
    candidate = design(conditions=(bva("north of 10 000", Operator.LT),))
    custom: Lexicon = {Operator.GT: ("north of",)}

    assert kinds(findings(candidate)) == []
    assert kinds(findings(candidate, custom)) == [FindingType.OPERATOR_MISMATCH]


def test_findings_come_in_the_order_of_the_checks() -> None:
    candidate = design(
        test_cases=(
            case("TC-1", {"amount": "5"}),
            case("TC-2", {"amount": "5"}, requirements=("S-1.R9",)),
        ),
        contradictions=(Contradiction(case_ids=("TC-1", "TC-2")),),
        conditions=(bva("over 10 000", Operator.GE),),
    )

    assert kinds(findings(candidate)) == [
        FindingType.MISSING_COVERAGE,
        FindingType.MISSING_COVERAGE,
        FindingType.UNTRACEABLE,
        FindingType.DUPLICATE,
        FindingType.CONTRADICTION,
        FindingType.OPERATOR_MISMATCH,
    ]
