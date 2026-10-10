from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictStr


class FindingType(StrEnum):
    MISSING_COVERAGE = "missing_coverage"
    UNTRACEABLE = "untraceable"
    DUPLICATE = "duplicate"
    CONTRADICTION = "contradiction"
    OPERATOR_MISMATCH = "operator_mismatch"


class Severity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: FindingType
    severity: Severity
    references: tuple[StrictStr, ...]
    message: StrictStr


def finding(type_: FindingType, references: tuple[str, ...], message: str) -> Finding:
    """A deterministic Finding: only a Contradiction blocks, the others warn."""
    severity = Severity.BLOCKING if type_ is FindingType.CONTRADICTION else Severity.WARNING
    return Finding(type=type_, severity=severity, references=references, message=message)
