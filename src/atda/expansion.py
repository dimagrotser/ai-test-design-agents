import operator as py
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.scalar import Scalar
from atda.schemas.test_condition import BvaCondition, Operator
from atda.schemas.test_design import TestCase

STEPS = {"integer": Decimal(1), "decimal": Decimal("0.01")}
POSITIONS = ("just below", "on", "just above")
COMPARISONS: dict[Operator, Callable[[Decimal, Decimal], bool]] = {
    Operator.GT: py.gt,
    Operator.GE: py.ge,
    Operator.LT: py.lt,
    Operator.LE: py.le,
    Operator.EQ: py.eq,
}


class ExpansionError(ValueError):
    pass


def expand(
    conditions: Sequence[BvaCondition],
    requirements: Sequence[Requirement],
    nominal_input: Mapping[str, Scalar],
) -> tuple[TestCase, ...]:
    ac_of = {requirement.id: requirement.ac_id for requirement in requirements}
    cases: list[TestCase] = []
    for condition in conditions:
        if condition.requirement_id not in ac_of:
            raise ExpansionError(f"unknown requirement id {condition.requirement_id}")
        if condition.input_name not in nominal_input:
            raise ExpansionError(f"input {condition.input_name} is not in the Nominal Input")
        for value, expected, rationale in _boundary_points(condition):
            cases.append(
                TestCase(
                    id=f"TC-{len(cases) + 1}",
                    requirement_ids=(condition.requirement_id,),
                    ac_ids=(ac_of[condition.requirement_id],),
                    technique=condition.technique,
                    rationale=rationale,
                    overrides={condition.input_name: value},
                    expected=expected,
                )
            )
    return tuple(cases)


def _boundary_points(condition: BvaCondition) -> list[tuple[Scalar, ExpectedOutcome, str]]:
    boundary = condition.boundary
    step = STEPS[condition.value_type]
    holds = COMPARISONS[condition.operator]
    points = []
    for position, value in zip(
        POSITIONS, (boundary - step, boundary, boundary + step), strict=True
    ):
        expected = (
            condition.outcome_if_true if holds(value, boundary) else condition.outcome_if_false
        )
        rationale = (
            f"boundary {_plain(boundary)} of {condition.input_name} "
            f"({condition.operator.value}): {position}"
        )
        scalar: Scalar = int(value) if condition.value_type == "integer" else _plain(value)
        points.append((scalar, expected, rationale))
    return points


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")
