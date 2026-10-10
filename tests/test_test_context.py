import pytest

from atda.schemas.test_context import TestContext, TestContextError, parse_test_context

VALID = """\
target: fraud.evaluate
nominal_input:
  amount: "100"
  currency: EUR
  country: DE
  recent_transactions: 0
statuses:
  - approved
  - rejected
outcome_keys:
  - amount_limit
  - blocked_country
  - velocity
"""


def test_context_keeps_target_nominal_input_and_outcome_keys() -> None:
    context = parse_test_context(VALID, "fraud.context.yaml")

    assert context == TestContext(
        target="fraud.evaluate",
        nominal_input={
            "amount": "100",
            "currency": "EUR",
            "country": "DE",
            "recent_transactions": 0,
        },
        statuses=("approved", "rejected"),
        outcome_keys=("amount_limit", "blocked_country", "velocity"),
    )


def test_an_unquoted_country_code_stays_text() -> None:
    context = parse_test_context(VALID.replace("country: DE", "country: NO"), "ctx.yaml")

    assert context.nominal_input["country"] == "NO"


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        (VALID.replace("target: fraud.evaluate\n", ""), "target"),
        (VALID.replace("nominal_input:", "nominal:"), "nominal_input"),
        (VALID.replace("statuses:\n  - approved\n  - rejected\n", ""), "statuses"),
        (VALID.replace("  - approved\n  - rejected\n", "  []\n"), "statuses"),
        (VALID.replace("  - rejected\n", "  - approved\n"), "duplicate status approved"),
        (VALID.split("outcome_keys:")[0], "outcome_keys"),
        (VALID.split("outcome_keys:")[0] + "outcome_keys: []\n", "outcome_keys"),
        (VALID + "  - velocity\n", "duplicate outcome key velocity"),
        (VALID + "outcome_key: typo\n", "outcome_key"),
        (VALID.replace("  currency: EUR\n", "  currency: [EUR]\n"), "nominal_input"),
        ("target: [unclosed\n", "not valid YAML"),
        ("- just\n- a list\n", "must be a mapping"),
        ("", "must be a mapping"),
    ],
)
def test_malformed_context_names_the_file_and_the_problem(source: str, problem: str) -> None:
    with pytest.raises(TestContextError) as error:
        parse_test_context(source, "eval/ctx.yaml")

    assert str(error.value).startswith("eval/ctx.yaml: ")
    assert problem in str(error.value)
