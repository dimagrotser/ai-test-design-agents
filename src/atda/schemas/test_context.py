import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    ValidationInfo,
    field_validator,
)

from atda.schemas.scalar import Scalar
from atda.schemas.strict_yaml import load_yaml
from atda.schemas.validation import format_validation_error


class TestContextError(ValueError):
    pass


class TestContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target: StrictStr = Field(min_length=1)
    nominal_input: dict[str, Scalar]
    statuses: tuple[StrictStr, ...] = Field(min_length=1)
    outcome_keys: tuple[StrictStr, ...] = Field(min_length=1)

    @field_validator("statuses", "outcome_keys")
    @classmethod
    def _names_are_unique(cls, names: tuple[str, ...], info: ValidationInfo) -> tuple[str, ...]:
        label = "status" if info.field_name == "statuses" else "outcome key"
        for name in names:
            if names.count(name) > 1:
                raise ValueError(f"duplicate {label} {name}")
        return names


def parse_test_context(source: str, name: str) -> TestContext:
    try:
        raw = load_yaml(source)
    except yaml.YAMLError as error:
        raise TestContextError(f"{name}: not valid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise TestContextError(f"{name}: the top level must be a mapping")
    try:
        return TestContext.model_validate(raw)
    except ValidationError as error:
        raise TestContextError(f"{name}: {format_validation_error(error)}") from error
