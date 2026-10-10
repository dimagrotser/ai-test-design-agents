from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.scalar import Scalar


class Technique(StrEnum):
    EP = "EP"
    BVA = "BVA"
    DECISION_TABLE = "DECISION_TABLE"


class Operator(StrEnum):
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "=="


class BvaCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    technique: Literal[Technique.BVA] = Technique.BVA
    requirement_id: StrictStr = Field(min_length=1)
    input_name: StrictStr = Field(min_length=1)
    evidence: StrictStr = Field(min_length=1)
    operator: Operator
    boundary: Decimal = Field(allow_inf_nan=False)
    value_type: Literal["integer", "decimal"]
    outcome_if_true: ExpectedOutcome
    outcome_if_false: ExpectedOutcome

    @model_validator(mode="after")
    def _integer_boundary_is_whole(self) -> Self:
        if self.value_type == "integer" and self.boundary != self.boundary.to_integral_value():
            raise ValueError("boundary must be a whole number when value_type is integer")
        return self


class EquivalenceClass(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: StrictStr = Field(min_length=1)
    values: tuple[Scalar, ...] = Field(min_length=1)
    outcome: ExpectedOutcome


class EpCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    technique: Literal[Technique.EP] = Technique.EP
    requirement_id: StrictStr = Field(min_length=1)
    input_name: StrictStr = Field(min_length=1)
    evidence: StrictStr = Field(min_length=1)
    classes: tuple[EquivalenceClass, ...] = Field(min_length=2)


class DecisionTableCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    technique: Literal[Technique.DECISION_TABLE] = Technique.DECISION_TABLE
    requirement_id: StrictStr = Field(min_length=1)
    evidence: StrictStr = Field(min_length=1)
    inputs: tuple[StrictStr, ...] = Field(min_length=2, max_length=4)

    @field_validator("inputs")
    @classmethod
    def _inputs_are_unique(cls, inputs: tuple[str, ...]) -> tuple[str, ...]:
        for name in inputs:
            if inputs.count(name) > 1:
                raise ValueError(f"duplicate input {name}")
        return inputs


TestCondition = Annotated[BvaCondition | EpCondition, Field(discriminator="technique")]
