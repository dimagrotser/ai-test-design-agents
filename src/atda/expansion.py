import operator as py
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Requirement
from atda.schemas.scalar import Scalar
from atda.schemas.test_condition import (
    BvaCondition,
    DecisionTableCondition,
    EpCondition,
    Operator,
)
from atda.schemas.test_design import TestCase

STEPS = {"integer": Decimal(1), "decimal": Decimal("0.01")}
POSITIONS = ("just below", "on", "just above")
SMALL_CLASS = 5
COMPARISONS: dict[Operator, Callable[[Decimal, Decimal], bool]] = {
    Operator.GT: py.gt,
    Operator.GE: py.ge,
    Operator.LT: py.lt,
    Operator.LE: py.le,
    Operator.EQ: py.eq,
}

Condition = BvaCondition | EpCondition | DecisionTableCondition
Point = tuple[dict[str, Scalar], ExpectedOutcome, str]


class ExpansionError(ValueError):
    pass


@dataclass(frozen=True)
class _Factor:
    """One input of a Decision Table: the value that fires its rule and what each side means."""

    name: str
    true_value: Scalar
    true_outcome: ExpectedOutcome
    false_outcome: ExpectedOutcome


def expand(
    conditions: Sequence[Condition],
    requirements: Sequence[Requirement],
    nominal_input: Mapping[str, Scalar],
) -> tuple[TestCase, ...]:
    ac_of = {requirement.id: requirement.ac_id for requirement in requirements}
    for condition in conditions:
        if condition.requirement_id not in ac_of:
            raise ExpansionError(f"unknown requirement id {condition.requirement_id}")
        if not isinstance(condition, DecisionTableCondition) and (
            condition.input_name not in nominal_input
        ):
            raise ExpansionError(f"input {condition.input_name} is not in the Nominal Input")
    problems = table_problems(conditions, nominal_input)
    if problems:
        raise ExpansionError("; ".join(problems))

    cases: list[TestCase] = []
    for condition in conditions:
        if isinstance(condition, DecisionTableCondition):
            points = _table_points(condition, conditions, nominal_input)
        elif isinstance(condition, BvaCondition):
            points = _boundary_points(condition)
        else:
            points = _class_points(condition)
        for overrides, expected, rationale in points:
            cases.append(
                TestCase(
                    id=f"TC-{len(cases) + 1}",
                    requirement_ids=(condition.requirement_id,),
                    ac_ids=(ac_of[condition.requirement_id],),
                    technique=condition.technique,
                    rationale=rationale,
                    overrides=overrides,
                    expected=expected,
                )
            )
    return tuple(cases)


def table_problems(
    conditions: Sequence[Condition], nominal_input: Mapping[str, Scalar]
) -> list[str]:
    problems: list[str] = []
    for condition in conditions:
        if isinstance(condition, DecisionTableCondition):
            problems += _derive(condition, conditions, nominal_input)[1]
    return problems


def _derive(
    table: DecisionTableCondition,
    conditions: Sequence[Condition],
    nominal_input: Mapping[str, Scalar],
) -> tuple[list[_Factor], list[str]]:
    label = f"decision table on {', '.join(table.inputs)}"
    factors: list[_Factor] = []
    problems: list[str] = []
    for name in table.inputs:
        if name not in nominal_input:
            problems.append(f"{label}: input {name} is not in the Nominal Input")
            continue
        related = next(
            (
                c
                for c in conditions
                if not isinstance(c, DecisionTableCondition) and c.input_name == name
            ),
            None,
        )
        if related is None:
            problems.append(f"{label}: input {name} has no BVA or EP condition")
            continue
        factor = _factor(name, related, nominal_input[name])
        if isinstance(factor, str):
            problems.append(f"{label}: {factor}")
        else:
            factors.append(factor)
    for side, statuses in (
        ("when a rule fires", [f.true_outcome.status for f in factors]),
        ("when no rule fires", [f.false_outcome.status for f in factors]),
    ):
        distinct = list(dict.fromkeys(statuses))
        if len(distinct) > 1:
            problems.append(f"{label}: inputs disagree on the status {side}: {', '.join(distinct)}")
    return factors, problems


def _factor(name: str, related: BvaCondition | EpCondition, nominal: Scalar) -> _Factor | str:
    already = f"input {name}: the Nominal value {nominal!r} already satisfies the rule"
    if isinstance(related, BvaCondition):
        number = _number(nominal)
        if number is None:
            return f"input {name}: the Nominal value {nominal!r} is not a number"
        holds = COMPARISONS[related.operator]
        if holds(number, related.boundary):
            return already
        step = STEPS[related.value_type]
        true_side = [v for v in _around(related.boundary, step) if holds(v, related.boundary)]
        nearest = min(true_side, key=lambda v: abs(v - related.boundary))
        return _Factor(
            name, _bva_value(related, nearest), related.outcome_if_true, related.outcome_if_false
        )
    firing = [c for c in related.classes if c.outcome.outcome_keys]
    quiet = [c for c in related.classes if not c.outcome.outcome_keys]
    if not firing:
        return f"input {name}: no class of its EP condition has Outcome Keys"
    if not quiet:
        return f"input {name}: every class of its EP condition has Outcome Keys"
    if nominal in {value for c in firing for value in c.values}:
        return already
    return _Factor(name, firing[0].values[0], firing[0].outcome, quiet[0].outcome)


def _table_points(
    table: DecisionTableCondition,
    conditions: Sequence[Condition],
    nominal_input: Mapping[str, Scalar],
) -> list[Point]:
    factors, _ = _derive(table, conditions, nominal_input)
    points: list[Point] = []
    for row in range(2 ** len(factors)):
        # The first input is the most significant bit, so rows count up from all false.
        fires = [bool(row >> (len(factors) - 1 - i) & 1) for i in range(len(factors))]
        fired = [f for f, fire in zip(factors, fires, strict=True) if fire]
        if fired:
            keys = tuple(k for f in fired for k in f.true_outcome.outcome_keys)
            expected = ExpectedOutcome(status=fired[0].true_outcome.status, outcome_keys=keys)
        else:
            expected = ExpectedOutcome(status=factors[0].false_outcome.status, outcome_keys=())
        states = ", ".join(
            f"{f.name} {'true' if fire else 'false'}"
            for f, fire in zip(factors, fires, strict=True)
        )
        points.append(
            (
                {f.name: f.true_value for f in fired},
                expected,
                f"decision table row {row + 1}: {states}",
            )
        )
    return points


def _boundary_points(condition: BvaCondition) -> list[Point]:
    boundary = condition.boundary
    holds = COMPARISONS[condition.operator]
    points: list[Point] = []
    values = _around(boundary, STEPS[condition.value_type])
    for position, value in zip(POSITIONS, values, strict=True):
        expected = (
            condition.outcome_if_true if holds(value, boundary) else condition.outcome_if_false
        )
        rationale = (
            f"boundary {_plain(boundary)} of {condition.input_name} "
            f"({condition.operator.value}): {position}"
        )
        points.append(({condition.input_name: _bva_value(condition, value)}, expected, rationale))
    return points


def _class_points(condition: EpCondition) -> list[Point]:
    points: list[Point] = []
    for equivalence_class in condition.classes:
        values = equivalence_class.values
        # A large class is represented by its first value.
        for value in values if len(values) <= SMALL_CLASS else values[:1]:
            rationale = f"class '{equivalence_class.name}' of {condition.input_name}: {value}"
            points.append(({condition.input_name: value}, equivalence_class.outcome, rationale))
    return points


def _around(boundary: Decimal, step: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    return boundary - step, boundary, boundary + step


def _bva_value(condition: BvaCondition, value: Decimal) -> Scalar:
    return int(value) if condition.value_type == "integer" else _plain(value)


def _number(value: Scalar) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")
