from decimal import Decimal
from typing import Literal

import pytest

from atda.expansion import ExpansionError, expand
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.scalar import Scalar
from atda.schemas.test_condition import BvaCondition, Operator, Technique

ValueType = Literal["integer", "decimal"]

REQUIREMENTS = (
    Requirement(id="S-1.R1", ac_id="AC-1", text="Over the limit is rejected."),
    Requirement(id="S-1.R2", ac_id="AC-2", text="Blocked countries are rejected."),
    Requirement(id="S-1.R3", ac_id="AC-3", text="Too many recent transactions are rejected."),
)
NOMINAL: dict[str, Scalar] = {"amount": "100", "country": "DE", "recent_transactions": 0}
APPROVED = ExpectedOutcome(status="approved", outcome_keys=())
REJECTED = ExpectedOutcome(status="rejected", outcome_keys=("amount_limit",))


def bva(
    operator: Operator,
    boundary: str,
    value_type: ValueType = "decimal",
    input_name: str = "amount",
    requirement_id: str = "S-1.R1",
) -> BvaCondition:
    return BvaCondition(
        requirement_id=requirement_id,
        input_name=input_name,
        evidence="over 10 000",
        operator=operator,
        boundary=Decimal(boundary),
        value_type=value_type,
        outcome_if_true=REJECTED,
        outcome_if_false=APPROVED,
    )


@pytest.mark.parametrize(
    ("operator", "boundary", "value_type", "name", "values", "holds"),
    [
        (Operator.GT, "10000", "decimal", "amount", ["9999.99", "10000", "10000.01"], "FFT"),
        (Operator.GE, "5", "integer", "recent_transactions", [4, 5, 6], "FTT"),
        (Operator.LT, "5", "integer", "recent_transactions", [4, 5, 6], "TFF"),
        (Operator.LE, "5", "integer", "recent_transactions", [4, 5, 6], "TTF"),
        (Operator.EQ, "5", "integer", "recent_transactions", [4, 5, 6], "FTF"),
    ],
)
def test_a_boundary_expands_to_three_points_with_the_outcomes_the_operator_implies(
    operator: Operator,
    boundary: str,
    value_type: ValueType,
    name: str,
    values: list[str | int],
    holds: str,
) -> None:
    cases = expand([bva(operator, boundary, value_type, name)], REQUIREMENTS, NOMINAL)

    assert [c.overrides for c in cases] == [{name: value} for value in values]
    assert [c.expected for c in cases] == [REJECTED if h == "T" else APPROVED for h in holds]


def test_decimal_values_are_exact_strings_and_the_boundary_is_not_padded() -> None:
    cases = expand([bva(Operator.GE, "10000.0")], REQUIREMENTS, NOMINAL)
    small = expand([bva(Operator.GE, "0.05")], REQUIREMENTS, NOMINAL)

    assert [c.overrides["amount"] for c in cases] == ["9999.99", "10000", "10000.01"]
    assert [c.overrides["amount"] for c in small] == ["0.04", "0.05", "0.06"]


def test_every_bva_case_names_its_technique_links_and_boundary_position() -> None:
    cases = expand([bva(Operator.GT, "10000")], REQUIREMENTS, NOMINAL)

    assert {c.technique for c in cases} == {Technique.BVA}
    assert {(c.requirement_ids, c.ac_ids) for c in cases} == {(("S-1.R1",), ("AC-1",))}
    assert [c.rationale for c in cases] == [
        "boundary 10000 of amount (>): just below",
        "boundary 10000 of amount (>): on",
        "boundary 10000 of amount (>): just above",
    ]


def test_ids_run_through_all_conditions_in_order_and_the_output_is_deterministic() -> None:
    conditions = [
        bva(Operator.GT, "10000"),
        bva(Operator.GE, "5", "integer", "recent_transactions", "S-1.R3"),
    ]

    first = expand(conditions, REQUIREMENTS, NOMINAL)
    second = expand(conditions, REQUIREMENTS, NOMINAL)

    assert [c.id for c in first] == [f"TC-{n}" for n in range(1, 7)]
    assert [c.ac_ids for c in first][3:] == [("AC-3",)] * 3
    assert first == second


def test_an_unknown_requirement_is_reported() -> None:
    with pytest.raises(ExpansionError, match="unknown requirement id S-1.R9"):
        expand([bva(Operator.GT, "1", requirement_id="S-1.R9")], REQUIREMENTS, NOMINAL)


def test_an_input_missing_from_the_nominal_input_is_reported() -> None:
    with pytest.raises(ExpansionError, match="input velocity is not in the Nominal Input"):
        expand([bva(Operator.GT, "1", input_name="velocity")], REQUIREMENTS, NOMINAL)
