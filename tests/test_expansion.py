from decimal import Decimal
from typing import Literal

import pytest

from atda.expansion import ExpansionError, expand, table_problems
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.scalar import Scalar
from atda.schemas.test_condition import (
    BvaCondition,
    DecisionTableCondition,
    EpCondition,
    EquivalenceClass,
    Operator,
    Technique,
)
from atda.schemas.test_design import TestCase

ValueType = Literal["integer", "decimal"]

REQUIREMENTS = (
    Requirement(id="S-1.R1", ac_id="AC-1", text="Over the limit is rejected."),
    Requirement(id="S-1.R2", ac_id="AC-2", text="Blocked countries are rejected."),
    Requirement(id="S-1.R3", ac_id="AC-3", text="Too many recent transactions are rejected."),
    Requirement(id="S-1.R4", ac_id="AC-4", text="Every broken rule is reported."),
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
    if_true: ExpectedOutcome = REJECTED,
) -> BvaCondition:
    return BvaCondition(
        requirement_id=requirement_id,
        input_name=input_name,
        evidence="over 10 000",
        operator=operator,
        boundary=Decimal(boundary),
        value_type=value_type,
        outcome_if_true=if_true,
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


def ep(
    *classes: tuple[str, tuple[Scalar, ...], ExpectedOutcome], input_name: str = "country"
) -> EpCondition:
    return EpCondition(
        requirement_id="S-1.R2",
        input_name=input_name,
        evidence="from KP, IR or SY",
        classes=tuple(EquivalenceClass(name=n, values=v, outcome=o) for n, v, o in classes),
    )


BLOCKED = ExpectedOutcome(status="rejected", outcome_keys=("blocked_country",))


def test_an_enumerated_class_and_an_other_class_give_one_case_per_member_plus_the_other() -> None:
    condition = ep(("blocked", ("KP", "IR", "SY"), BLOCKED), ("other", ("DE",), APPROVED))

    cases = expand([condition], REQUIREMENTS, NOMINAL)

    assert [c.overrides for c in cases] == [{"country": v} for v in ("KP", "IR", "SY", "DE")]
    assert [c.expected for c in cases] == [BLOCKED, BLOCKED, BLOCKED, APPROVED]
    assert {c.technique for c in cases} == {Technique.EP}
    assert {(c.requirement_ids, c.ac_ids) for c in cases} == {(("S-1.R2",), ("AC-2",))}
    assert cases[0].rationale == "class 'blocked' of country: KP"
    assert cases[3].rationale == "class 'other' of country: DE"


@pytest.mark.parametrize(("size", "used"), [(5, 5), (6, 1)])
def test_a_small_class_is_used_in_full_and_a_large_one_by_its_representative(
    size: int, used: int
) -> None:
    members = tuple(f"C{n}" for n in range(size))
    condition = ep(("big", members, BLOCKED), ("other", ("DE",), APPROVED))

    cases = expand([condition], REQUIREMENTS, NOMINAL)

    assert [c.overrides["country"] for c in cases] == [*members[:used], "DE"]


def test_ep_and_bva_cases_share_one_id_sequence_in_condition_order() -> None:
    conditions: list[BvaCondition | EpCondition] = [
        ep(("blocked", ("KP",), BLOCKED), ("other", ("DE",), APPROVED)),
        bva(Operator.GT, "10000"),
    ]

    cases = expand(conditions, REQUIREMENTS, NOMINAL)

    assert [c.id for c in cases] == ["TC-1", "TC-2", "TC-3", "TC-4", "TC-5"]
    assert [c.technique for c in cases] == [Technique.EP] * 2 + [Technique.BVA] * 3


def test_an_ep_input_missing_from_the_nominal_input_is_reported() -> None:
    condition = ep(("a", ("x",), BLOCKED), ("b", ("y",), APPROVED), input_name="region")

    with pytest.raises(ExpansionError, match="input region is not in the Nominal Input"):
        expand([condition], REQUIREMENTS, NOMINAL)


VELOCITY = ExpectedOutcome(status="rejected", outcome_keys=("velocity",))


def table(*inputs: str) -> DecisionTableCondition:
    return DecisionTableCondition(
        requirement_id="S-1.R4", evidence="every broken rule", inputs=inputs
    )


def fraud_rules() -> list[BvaCondition | EpCondition | DecisionTableCondition]:
    return [
        bva(Operator.GT, "10000"),
        ep(("blocked", ("KP", "IR", "SY"), BLOCKED), ("other", ("DE",), APPROVED)),
        bva(Operator.GE, "5", "integer", "recent_transactions", "S-1.R3", VELOCITY),
        table("amount", "country", "recent_transactions"),
    ]


def rows() -> list[TestCase]:
    return [
        c
        for c in expand(fraud_rules(), REQUIREMENTS, NOMINAL)
        if c.technique is Technique.DECISION_TABLE
    ]


def test_three_inputs_give_eight_rows_holding_only_their_true_inputs() -> None:
    cases = rows()

    assert [c.overrides for c in cases] == [
        {},
        {"recent_transactions": 5},
        {"country": "KP"},
        {"country": "KP", "recent_transactions": 5},
        {"amount": "10000.01"},
        {"amount": "10000.01", "recent_transactions": 5},
        {"amount": "10000.01", "country": "KP"},
        {"amount": "10000.01", "country": "KP", "recent_transactions": 5},
    ]


def test_a_row_outcome_is_the_union_of_the_keys_of_the_inputs_that_fire() -> None:
    cases = rows()

    assert cases[0].expected == APPROVED
    assert cases[5].expected == ExpectedOutcome(
        status="rejected", outcome_keys=("amount_limit", "velocity")
    )
    assert cases[7].expected.outcome_keys == ("amount_limit", "blocked_country", "velocity")
    assert cases[7].expected.status == "rejected"


def test_a_row_names_its_technique_links_and_position() -> None:
    cases = rows()

    assert {c.technique for c in cases} == {Technique.DECISION_TABLE}
    assert {(c.requirement_ids, c.ac_ids) for c in cases} == {(("S-1.R4",), ("AC-4",))}
    assert cases[0].rationale == (
        "decision table row 1: amount false, country false, recent_transactions false"
    )
    assert cases[5].rationale == (
        "decision table row 6: amount true, country false, recent_transactions true"
    )


def test_all_cases_share_one_id_sequence_with_the_table_after_its_inputs() -> None:
    cases = expand(fraud_rules(), REQUIREMENTS, NOMINAL)

    assert len(cases) == 3 + 4 + 3 + 8
    assert [c.id for c in cases][-1] == "TC-18"


@pytest.mark.parametrize(
    ("operator", "true_value"),
    [(Operator.GT, 6), (Operator.GE, 5), (Operator.LT, 4), (Operator.LE, 5), (Operator.EQ, 5)],
)
def test_the_true_value_is_the_true_side_point_nearest_the_boundary(
    operator: Operator, true_value: int
) -> None:
    conditions: list[BvaCondition | EpCondition | DecisionTableCondition] = [
        bva(Operator.GT, "10000"),
        bva(operator, "5", "integer", "recent_transactions", "S-1.R3", VELOCITY),
        table("amount", "recent_transactions"),
    ]
    # The Nominal value must sit on the false side of the rule.
    below = operator in (Operator.LT, Operator.LE)
    nominal: dict[str, Scalar] = {**NOMINAL, "recent_transactions": 100 if below else 0}
    cases = [
        c
        for c in expand(conditions, REQUIREMENTS, nominal)
        if c.technique is Technique.DECISION_TABLE
    ]

    assert cases[1].overrides == {"recent_transactions": true_value}


def test_a_table_input_without_a_single_factor_condition_is_reported() -> None:
    conditions: list[BvaCondition | EpCondition | DecisionTableCondition] = [
        bva(Operator.GT, "10000"),
        table("amount", "country"),
    ]

    problems = table_problems(conditions, NOMINAL)

    assert problems == [
        "decision table on amount, country: input country has no BVA or EP condition"
    ]
    with pytest.raises(ExpansionError, match="input country has no BVA or EP condition"):
        expand(conditions, REQUIREMENTS, NOMINAL)


def test_a_table_input_missing_from_the_nominal_input_is_reported() -> None:
    conditions: list[BvaCondition | EpCondition | DecisionTableCondition] = [
        bva(Operator.GT, "10000"),
        table("amount", "region"),
    ]

    assert any(
        "input region is not in the Nominal Input" in p for p in table_problems(conditions, NOMINAL)
    )


def test_a_nominal_value_that_already_breaks_the_rule_is_reported() -> None:
    nominal: dict[str, Scalar] = {**NOMINAL, "amount": "20000", "country": "KP"}

    problems = table_problems(fraud_rules(), nominal)

    assert any("amount" in p and "already satisfies the rule" in p for p in problems)
    assert any("country" in p and "already satisfies the rule" in p for p in problems)


def test_inputs_that_disagree_on_the_status_of_a_broken_rule_are_reported() -> None:
    flagged = ExpectedOutcome(status="flagged", outcome_keys=("velocity",))
    conditions: list[BvaCondition | EpCondition | DecisionTableCondition] = [
        bva(Operator.GT, "10000"),
        bva(Operator.GE, "5", "integer", "recent_transactions", "S-1.R3", flagged),
        table("amount", "recent_transactions"),
    ]

    problems = table_problems(conditions, NOMINAL)

    assert any("disagree on the status" in p for p in problems)


def test_a_valid_set_of_conditions_has_no_table_problems() -> None:
    assert table_problems(fraud_rules(), NOMINAL) == []
