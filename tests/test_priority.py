import pytest
from pydantic import ValidationError

from atda.priority import priority_of, with_priorities
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.risk import Priority, Risk
from atda.schemas.test_condition import Technique
from atda.schemas.test_design import TestCase, TestDesign


@pytest.mark.parametrize(
    ("likelihood", "impact", "expected"),
    [
        (1, 1, Priority.P3),
        (1, 2, Priority.P3),
        (1, 3, Priority.P2),
        (2, 1, Priority.P3),
        (2, 2, Priority.P2),
        (2, 3, Priority.P1),
        (3, 1, Priority.P2),
        (3, 2, Priority.P1),
        (3, 3, Priority.P1),
    ],
)
def test_each_likelihood_and_impact_cell_maps_to_its_priority(
    likelihood: int, impact: int, expected: Priority
) -> None:
    assert priority_of(Risk(likelihood=likelihood, impact=impact)) is expected


@pytest.mark.parametrize("bad", [0, 4, -1, "2", 2.0, True])
@pytest.mark.parametrize("field", ["likelihood", "impact"])
def test_a_score_outside_one_to_three_or_not_an_integer_is_rejected(
    field: str, bad: object
) -> None:
    scores = {"likelihood": 2, "impact": 2, field: bad}

    with pytest.raises(ValidationError, match=field):
        Risk.model_validate(scores)


def requirement(requirement_id: str, risk: Risk | None) -> Requirement:
    return Requirement(id=requirement_id, ac_id="AC-1", text="x", risk=risk)


def case(case_id: str, requirement_ids: tuple[str, ...]) -> TestCase:
    return TestCase(
        id=case_id,
        requirement_ids=requirement_ids,
        ac_ids=("AC-1",),
        technique=Technique.BVA,
        rationale="why",
        overrides={},
        expected=ExpectedOutcome(status="ok", outcome_keys=()),
    )


def design(requirements: tuple[Requirement, ...], cases: tuple[TestCase, ...]) -> TestDesign:
    return TestDesign(story_id="S-1", requirements=requirements, gaps=(), test_cases=cases)


def test_a_test_case_takes_the_priority_of_its_requirement() -> None:
    result = with_priorities(
        design(
            (
                requirement("R1", Risk(likelihood=3, impact=3)),
                requirement("R2", Risk(likelihood=1, impact=1)),
            ),
            (case("TC-1", ("R1",)), case("TC-2", ("R2",))),
        )
    )

    assert [c.priority for c in result.test_cases] == [Priority.P1, Priority.P3]


def test_a_merged_test_case_takes_the_highest_priority_of_its_requirements() -> None:
    result = with_priorities(
        design(
            (
                requirement("R1", Risk(likelihood=1, impact=2)),
                requirement("R2", Risk(likelihood=2, impact=2)),
            ),
            (case("TC-1", ("R1", "R2")),),
        )
    )

    assert result.test_cases[0].priority is Priority.P2


def test_an_unrated_requirement_is_ignored_when_another_one_is_rated() -> None:
    result = with_priorities(
        design(
            (requirement("R1", None), requirement("R2", Risk(likelihood=1, impact=3))),
            (case("TC-1", ("R1", "R2")),),
        )
    )

    assert result.test_cases[0].priority is Priority.P2


def test_a_case_whose_requirements_are_all_unrated_has_no_priority() -> None:
    result = with_priorities(design((requirement("R1", None),), (case("TC-1", ("R1",)),)))

    assert result.test_cases[0].priority is None


def test_a_case_that_names_an_unknown_requirement_keeps_no_priority() -> None:
    result = with_priorities(
        design((requirement("R1", Risk(likelihood=3, impact=3)),), (case("TC-1", ("R9",)),))
    )

    assert result.test_cases[0].priority is None


def test_the_input_design_is_not_changed() -> None:
    original = design((requirement("R1", Risk(likelihood=3, impact=3)),), (case("TC-1", ("R1",)),))

    with_priorities(original)

    assert original.test_cases[0].priority is None


def test_a_document_written_before_risk_and_priority_existed_still_loads() -> None:
    older = {
        "story_id": "S-1",
        "requirements": [{"id": "R1", "ac_id": "AC-1", "text": "x"}],
        "gaps": [],
        "test_cases": [
            {
                "id": "TC-1",
                "requirement_ids": ["R1"],
                "ac_ids": ["AC-1"],
                "technique": "BVA",
                "rationale": "why",
                "overrides": {},
                "expected": {"status": "ok", "outcome_keys": []},
            }
        ],
    }

    loaded = TestDesign.model_validate(older)

    assert loaded.requirements[0].risk is None
    assert loaded.test_cases[0].priority is None


def test_risk_and_priority_survive_a_json_round_trip() -> None:
    rated = with_priorities(
        design((requirement("R1", Risk(likelihood=2, impact=3)),), (case("TC-1", ("R1",)),))
    )

    assert TestDesign.model_validate_json(rated.model_dump_json()) == rated
