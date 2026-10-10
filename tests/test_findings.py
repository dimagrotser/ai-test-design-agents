import pytest

from atda.schemas.findings import Finding, FindingType, Severity, finding


def test_a_contradiction_is_blocking() -> None:
    found = finding(FindingType.CONTRADICTION, ("TC-1", "TC-2"), "same input, different outcome")

    assert found.severity is Severity.BLOCKING
    assert found.references == ("TC-1", "TC-2")


@pytest.mark.parametrize(
    "type_",
    [
        FindingType.MISSING_COVERAGE,
        FindingType.UNTRACEABLE,
        FindingType.DUPLICATE,
        FindingType.OPERATOR_MISMATCH,
    ],
)
def test_every_other_type_only_warns(type_: FindingType) -> None:
    assert finding(type_, ("X-1",), "message").severity is Severity.WARNING


def test_a_finding_survives_a_json_round_trip() -> None:
    found = finding(FindingType.MISSING_COVERAGE, ("AC-3",), "AC-3 has no Test Case")

    assert Finding.model_validate_json(found.model_dump_json()) == found
