from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from atda.schemas.scalar import Scalar


class ExpectedOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: StrictStr = Field(min_length=1)
    outcome_keys: tuple[StrictStr, ...]
    values: dict[str, Scalar] | None = None

    @field_validator("outcome_keys")
    @classmethod
    def _sorted_and_unique(cls, keys: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(keys)))
