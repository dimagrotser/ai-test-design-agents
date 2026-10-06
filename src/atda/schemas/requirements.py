from pydantic import BaseModel, ConfigDict


class Requirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    ac_id: str
    text: str


class Gap(BaseModel):
    model_config = ConfigDict(frozen=True)

    ac_id: str | None = None
    text: str


class Analysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirements: tuple[Requirement, ...]
    gaps: tuple[Gap, ...]
