import pytest
from pydantic import ValidationError

from atda.schemas.outcome import ExpectedOutcome


def test_values_are_optional() -> None:
    outcome = ExpectedOutcome(status="approved", outcome_keys=())

    assert outcome.values is None


@pytest.mark.parametrize("value", ["text", 3, 2.5, True])
def test_values_accept_the_closed_set_of_scalars(value: str | int | float | bool) -> None:
    outcome = ExpectedOutcome(status="ok", outcome_keys=(), values={"x": value})

    assert outcome.values == {"x": value}
    assert type(outcome.values["x"]) is type(value)


@pytest.mark.parametrize("value", [[1], {"a": 1}, None], ids=["list", "mapping", "null"])
def test_values_reject_anything_that_is_not_a_scalar(value: object) -> None:
    with pytest.raises(ValidationError):
        ExpectedOutcome.model_validate({"status": "ok", "outcome_keys": [], "values": {"x": value}})


def test_outcome_keys_come_back_sorted_and_unique() -> None:
    outcome = ExpectedOutcome(
        status="rejected", outcome_keys=("velocity", "amount_limit", "velocity")
    )

    assert outcome.outcome_keys == ("amount_limit", "velocity")


def test_the_status_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        ExpectedOutcome(status="", outcome_keys=())


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExpectedOutcome.model_validate({"status": "ok", "outcome_keys": [], "reason": "why"})


def test_an_outcome_survives_a_json_round_trip() -> None:
    outcome = ExpectedOutcome(status="ok", outcome_keys=("a",), values={"limit": 5, "name": "x"})

    assert ExpectedOutcome.model_validate_json(outcome.model_dump_json()) == outcome
