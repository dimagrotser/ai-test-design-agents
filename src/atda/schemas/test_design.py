from pydantic import BaseModel, ConfigDict, Field, StrictStr

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Gap, Requirement
from atda.schemas.scalar import Scalar
from atda.schemas.test_condition import Technique


class TestCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: StrictStr = Field(min_length=1)
    requirement_ids: tuple[StrictStr, ...]
    ac_ids: tuple[StrictStr, ...]
    technique: Technique
    rationale: StrictStr
    overrides: dict[str, Scalar]
    expected: ExpectedOutcome


class TestDesign(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    story_id: StrictStr = Field(min_length=1)
    requirements: tuple[Requirement, ...]
    gaps: tuple[Gap, ...]
    test_cases: tuple[TestCase, ...]
