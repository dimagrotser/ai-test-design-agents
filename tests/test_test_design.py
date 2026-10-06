from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Gap, Requirement
from atda.schemas.test_condition import Technique
from atda.schemas.test_design import TestCase, TestDesign

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
