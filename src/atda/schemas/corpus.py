import re
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictStr,
    ValidationError,
    field_validator,
)

from atda.schemas.story import Story
from atda.schemas.strict_yaml import load_yaml
from atda.schemas.test_context import TestContext
from atda.schemas.validation import format_validation_error

FULL_SHA = re.compile(r"[0-9a-f]{40}")


class ManifestError(ValueError):
    pass


class HeldOutStoryError(ManifestError):
    pass


class StoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    story: StrictStr = Field(min_length=1)
    test_context: StrictStr = Field(min_length=1)
    sut_config: dict[str, JsonValue] = {}
    split: Literal["dev", "held-out"]
    story_class: Literal["normal", "gap-probe"] = Field(alias="class")


class CorpusManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sut_commit: StrictStr
    stories: dict[str, StoryEntry] = Field(min_length=1)

    @field_validator("sut_commit")
    @classmethod
    def _is_a_full_commit_sha(cls, value: str) -> str:
        if not FULL_SHA.fullmatch(value):
            raise ValueError(f"sut_commit must be a full 40-character commit SHA, got {value!r}")
        return value

    def require_dev(self, story_id: str) -> StoryEntry:
        entry = self.stories.get(story_id)
        if entry is None:
            raise ManifestError(f"unknown story id {story_id}")
        if entry.split == "held-out":
            raise HeldOutStoryError(
                f"{story_id} is a held-out Story and must not be recorded or tuned on"
            )
        return entry


class AgentView(BaseModel):
    """All an agent may see of an eval Story: no SUT Config, split or class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    story: Story
    test_context: TestContext


def parse_manifest(source: str, name: str) -> CorpusManifest:
    try:
        raw = load_yaml(source)
    except yaml.YAMLError as error:
        raise ManifestError(f"{name}: not valid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise ManifestError(f"{name}: the top level must be a mapping")
    try:
        return CorpusManifest.model_validate(raw)
    except ValidationError as error:
        raise ManifestError(f"{name}: {format_validation_error(error)}") from error
