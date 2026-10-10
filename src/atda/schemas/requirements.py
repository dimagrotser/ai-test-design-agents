from pydantic import BaseModel, ConfigDict

from atda.schemas.risk import Risk


class Requirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    ac_id: str
    text: str
    risk: Risk | None = None


class Gap(BaseModel):
    model_config = ConfigDict(frozen=True)

    ac_id: str | None = None
    text: str


class Analysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirements: tuple[Requirement, ...]
    gaps: tuple[Gap, ...]
