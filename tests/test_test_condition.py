import copy
from collections.abc import Mapping
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from atda.schemas.test_condition import (
    BvaCondition,
    DecisionTableCondition,
    EpCondition,
    Operator,
    Technique,
    TestCondition,
)

APPROVED = {"status": "approved", "outcome_keys": []}
REJECTED = {"status": "rejected", "outcome_keys": ["amount_limit"]}

BVA = {
    "technique": "BVA",
    "requirement_id": "S-1.R1",
    "input_name": "amount",
    "evidence": "over 10 000",
    "operator": ">",
    "boundary": 10000,
    "value_type": "decimal",
    "outcome_if_true": REJECTED,
    "outcome_if_false": APPROVED,
}

BLOCKED = {"name": "blocked", "values": ["KP", "IR", "SY"], "outcome": REJECTED}
OTHER = {"name": "other", "values": ["DE"], "outcome": APPROVED}

EP = {
    "technique": "EP",
    "requirement_id": "S-1.R2",
    "input_name": "country",
    "evidence": "from KP, IR or SY",
    "classes": [BLOCKED, OTHER],
}

condition: TypeAdapter[BvaCondition | EpCondition] = TypeAdapter(TestCondition)


def changed(base: Mapping[str, object], **updates: object) -> dict[str, object]:
    return {**copy.deepcopy(base), **updates}


def test_a_bva_condition_is_read_from_its_fields() -> None:
    parsed = condition.validate_python(BVA)

    assert isinstance(parsed, BvaCondition)
    assert parsed.operator is Operator.GT
    assert parsed.boundary == Decimal(10000)
    assert parsed.outcome_if_true.outcome_keys == ("amount_limit",)


def test_an_ep_condition_is_read_from_its_classes() -> None:
    parsed = condition.validate_python(EP)

    assert isinstance(parsed, EpCondition)
    assert [c.name for c in parsed.classes] == ["blocked", "other"]
    assert parsed.classes[0].values == ("KP", "IR", "SY")


def test_a_bva_condition_without_an_operator_is_rejected() -> None:
    without = {k: v for k, v in BVA.items() if k != "operator"}

    with pytest.raises(ValidationError, match="operator"):
        condition.validate_python(without)


@pytest.mark.parametrize("operator", ["!=", "greater", ""])
def test_an_unknown_operator_is_rejected(operator: str) -> None:
    with pytest.raises(ValidationError, match="operator"):
        condition.validate_python(changed(BVA, operator=operator))


@pytest.mark.parametrize("operator", [">", ">=", "<", "<=", "=="])
def test_every_operator_of_the_closed_set_is_accepted(operator: str) -> None:
    assert condition.validate_python(changed(BVA, operator=operator)).technique == "BVA"


def test_an_integer_boundary_must_be_a_whole_number() -> None:
    with pytest.raises(ValidationError, match="whole number"):
        condition.validate_python(changed(BVA, value_type="integer", boundary="5.5"))


def test_a_decimal_boundary_may_have_a_fraction() -> None:
    parsed = condition.validate_python(changed(BVA, boundary="0.05"))

    assert isinstance(parsed, BvaCondition)
    assert parsed.boundary == Decimal("0.05")


@pytest.mark.parametrize("boundary", ["NaN", "Infinity"])
def test_a_boundary_must_be_a_finite_number(boundary: str) -> None:
    with pytest.raises(ValidationError):
        condition.validate_python(changed(BVA, boundary=boundary))


def test_an_unknown_technique_is_rejected() -> None:
    with pytest.raises(ValidationError, match="technique"):
        condition.validate_python(changed(BVA, technique="PAIRWISE"))


def test_an_ep_condition_needs_at_least_two_classes() -> None:
    with pytest.raises(ValidationError, match="classes"):
        condition.validate_python(changed(EP, classes=[BLOCKED]))


def test_an_equivalence_class_needs_values() -> None:
    empty = [{"name": "blocked", "values": [], "outcome": REJECTED}, OTHER]

    with pytest.raises(ValidationError, match="values"):
        condition.validate_python(changed(EP, classes=empty))


def test_the_evidence_must_not_be_empty() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        condition.validate_python(changed(BVA, evidence=""))


@pytest.mark.parametrize("source", [BVA, EP], ids=["bva", "ep"])
def test_a_condition_survives_a_json_round_trip_with_its_type(source: Mapping[str, object]) -> None:
    parsed = condition.validate_python(source)

    again = condition.validate_json(condition.dump_json(parsed))

    assert again == parsed
    assert type(again) is type(parsed)


DT = {
    "technique": "DECISION_TABLE",
    "requirement_id": "S-1.R4",
    "evidence": "every broken rule",
    "inputs": ["amount", "country", "recent_transactions"],
}


def test_a_decision_table_names_the_inputs_it_combines() -> None:
    table = DecisionTableCondition.model_validate(DT)

    assert table.inputs == ("amount", "country", "recent_transactions")
    assert table.technique is Technique.DECISION_TABLE


@pytest.mark.parametrize("inputs", [["amount", "country"], ["a", "b", "c", "d"]])
def test_two_to_four_inputs_are_accepted(inputs: list[str]) -> None:
    assert len(DecisionTableCondition.model_validate(changed(DT, inputs=inputs)).inputs) >= 2


@pytest.mark.parametrize("inputs", [["amount"], ["a", "b", "c", "d", "e"]])
def test_fewer_than_two_or_more_than_four_inputs_are_rejected(inputs: list[str]) -> None:
    with pytest.raises(ValidationError, match="inputs"):
        DecisionTableCondition.model_validate(changed(DT, inputs=inputs))


def test_a_decision_table_cannot_list_an_input_twice() -> None:
    with pytest.raises(ValidationError, match="duplicate input amount"):
        DecisionTableCondition.model_validate(changed(DT, inputs=["amount", "country", "amount"]))
