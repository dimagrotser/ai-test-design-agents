from decimal import Decimal

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Gap, Requirement
from atda.schemas.test_condition import BvaCondition, Operator, Technique
from atda.schemas.test_design import Contradiction, TestCase, TestDesign

CASE = TestCase(
    id="TC-1",
    requirement_ids=("S-1.R1",),
    ac_ids=("AC-1",),
    technique=Technique.BVA,
    rationale="boundary 10000 of amount (>): just above",
    overrides={"amount": "10000.01"},
    expected=ExpectedOutcome(status="rejected", outcome_keys=("amount_limit",)),
)


def test_a_test_case_survives_a_json_round_trip() -> None:
    again = TestCase.model_validate_json(CASE.model_dump_json())

    assert again == CASE
    assert again.technique is Technique.BVA
    assert again.requirement_ids == ("S-1.R1",)


def test_a_test_design_keeps_requirements_gaps_and_cases_through_json() -> None:
    design = TestDesign(
        story_id="S-1",
        requirements=(Requirement(id="S-1.R1", ac_id="AC-1", text="Over the limit is rejected."),),
        gaps=(Gap(text="Currency is not stated."),),
        test_cases=(CASE,),
    )

    assert TestDesign.model_validate_json(design.model_dump_json()) == design


def test_the_duplicate_ratio_and_contradictions_survive_a_json_round_trip() -> None:
    design = TestDesign(
        story_id="S-1",
        requirements=(),
        gaps=(),
        test_cases=(CASE,),
        duplicate_ratio=0.25,
        contradictions=(Contradiction(case_ids=("TC-1", "TC-4")),),
    )

    assert TestDesign.model_validate_json(design.model_dump_json()) == design


def test_a_document_written_before_the_ratio_existed_still_loads() -> None:
    older = {"story_id": "S-1", "requirements": [], "gaps": [], "test_cases": []}

    design = TestDesign.model_validate(older)

    assert design.duplicate_ratio == 0.0
    assert design.contradictions == ()


def test_the_conditions_survive_a_json_round_trip_with_their_types() -> None:
    condition = BvaCondition(
        requirement_id="S-1.R1",
        input_name="amount",
        evidence="over 10 000",
        operator=Operator.GT,
        boundary=Decimal(10000),
        value_type="decimal",
        outcome_if_true=ExpectedOutcome(status="rejected", outcome_keys=("amount_limit",)),
        outcome_if_false=ExpectedOutcome(status="approved", outcome_keys=()),
    )
    design = TestDesign(
        story_id="S-1", requirements=(), gaps=(), test_cases=(CASE,), conditions=(condition,)
    )

    again = TestDesign.model_validate_json(design.model_dump_json())

    assert again == design
    assert isinstance(again.conditions[0], BvaCondition)


def test_a_document_without_conditions_loads_with_none() -> None:
    older = {"story_id": "S-1", "requirements": [], "gaps": [], "test_cases": []}

    assert TestDesign.model_validate(older).conditions == ()
