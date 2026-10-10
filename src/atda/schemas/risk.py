from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


Score = Annotated[int, Field(strict=True, ge=1, le=3)]


class Risk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    likelihood: Score
    impact: Score
