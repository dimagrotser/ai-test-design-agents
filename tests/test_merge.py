import pytest

from atda.merge import merge_duplicates
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.scalar import Scalar
from atda.schemas.test_condition import Technique
from atda.schemas.test_design import Contradiction, TestCase

NOMINAL: dict[str, Scalar] = {"amount": "100", "country": "DE", "recent_transactions": 0}
APPROVED = ExpectedOutcome(status="approved", outcome_keys=())
REJECTED = ExpectedOutcome(status="rejected", outcome_keys=("amount_limit",))


def case(
    case_id: str,
    overrides: dict[str, Scalar],
    expected: ExpectedOutcome = REJECTED,
    requirement: str = "S-1.R1",
    ac: str = "AC-1",
    technique: Technique = Technique.BVA,
    rationale: str = "why",
) -> TestCase:
    return TestCase(
        id=case_id,
        requirement_ids=(requirement,),
        ac_ids=(ac,),
        technique=technique,
        rationale=rationale,
        overrides=overrides,
        expected=expected,
    )


def test_a_table_row_that_repeats_a_boundary_case_merges_into_it() -> None:
    boundary = case("TC-1", {"amount": "10000.01"}, rationale="just above")
    row = case(
        "TC-9",
        {"amount": "10000.01"},
        requirement="S-1.R4",
        ac="AC-4",
        technique=Technique.DECISION_TABLE,
        rationale="row 5",
    )

    result = merge_duplicates([boundary, row], NOMINAL)

    (merged,) = result.cases
    assert merged.id == "TC-1"
    assert merged.technique is Technique.BVA
    assert merged.requirement_ids == ("S-1.R1", "S-1.R4")
    assert merged.ac_ids == ("AC-1", "AC-4")
    assert merged.rationale == "just above; row 5"
    assert merged.overrides == {"amount": "10000.01"}
    assert result.contradictions == ()


def test_the_ratio_is_one_minus_unique_over_total_taken_before_the_merge() -> None:
    cases = [
        case("TC-1", {"amount": "1"}),
        case("TC-2", {"amount": "1"}),
        case("TC-3", {"amount": "2"}),
    ]

    result = merge_duplicates(cases, NOMINAL)

    assert len(result.cases) == 2
    assert result.duplicate_ratio == pytest.approx(1 / 3)


def test_there_is_no_ratio_without_duplicates_or_without_cases() -> None:
    assert (
        merge_duplicates(
            [case("TC-1", {"amount": "1"}), case("TC-2", {"amount": "2"})], NOMINAL
        ).duplicate_ratio
        == 0
    )
    assert merge_duplicates([], NOMINAL).duplicate_ratio == 0


@pytest.mark.parametrize("other", ["10000", "10000.0", 10000, 10000.0])
def test_numbers_written_differently_are_the_same_input(other: Scalar) -> None:
    result = merge_duplicates(
        [case("TC-1", {"amount": "10000.0"}), case("TC-2", {"amount": other})], NOMINAL
    )

    assert len(result.cases) == 1


def test_a_text_with_a_leading_zero_is_not_a_number() -> None:
    result = merge_duplicates(
        [case("TC-1", {"customer": "007"}), case("TC-2", {"customer": "7"})],
        {**NOMINAL, "customer": "1"},
    )

    assert len(result.cases) == 2


def test_an_override_equal_to_the_nominal_value_is_the_same_as_no_override() -> None:
    result = merge_duplicates(
        [case("TC-1", {}, APPROVED), case("TC-2", {"country": "DE"}, APPROVED)], NOMINAL
    )

    assert [c.id for c in result.cases] == ["TC-1"]


def test_the_order_of_the_fields_does_not_matter() -> None:
    first = case("TC-1", {"amount": "5", "country": "KP"})
    second = case("TC-2", {"country": "KP", "amount": "5"})

    assert len(merge_duplicates([first, second], NOMINAL).cases) == 1


def test_the_same_input_with_different_outcomes_is_a_contradiction_and_both_cases_stay() -> None:
    first = case("TC-1", {"amount": "5"}, REJECTED)
    second = case("TC-2", {"amount": "5"}, APPROVED)

    result = merge_duplicates([first, second], NOMINAL)

    assert [c.id for c in result.cases] == ["TC-1", "TC-2"]
    assert result.contradictions == (Contradiction(case_ids=("TC-1", "TC-2")),)


def test_cases_that_agree_still_merge_inside_a_contradictory_group() -> None:
    cases = [
        case("TC-1", {"amount": "5"}, REJECTED),
        case("TC-2", {"amount": "5"}, APPROVED),
        case("TC-3", {"amount": "5"}, REJECTED, requirement="S-1.R4", ac="AC-4"),
    ]

    result = merge_duplicates(cases, NOMINAL)

    assert [c.id for c in result.cases] == ["TC-1", "TC-2"]
    assert result.cases[0].requirement_ids == ("S-1.R1", "S-1.R4")
    assert result.contradictions == (Contradiction(case_ids=("TC-1", "TC-2")),)


def test_surviving_cases_keep_their_order_and_ids() -> None:
    cases = [
        case("TC-1", {"amount": "1"}),
        case("TC-2", {"amount": "2"}),
        case("TC-3", {"amount": "1"}),
        case("TC-4", {"amount": "3"}),
    ]

    assert [c.id for c in merge_duplicates(cases, NOMINAL).cases] == ["TC-1", "TC-2", "TC-4"]
