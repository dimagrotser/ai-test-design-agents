import re
from typing import Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from atda.schemas.strict_yaml import load_yaml
from atda.schemas.validation import format_validation_error

_VARIABLE_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")
_ENDPOINT = re.compile(r"https?://\S+")


class ProviderProfileError(ValueError):
    pass


class ProviderProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter: StrictStr = Field(min_length=1)
    endpoint: StrictStr
    model: StrictStr = Field(min_length=1)
    structured_output: StrictStr = Field(min_length=1)
    context_size: int = Field(gt=0)
    timeout: float = Field(gt=0)
    location: Literal["local", "cloud"]
    key_variable: StrictStr | None

    @field_validator("endpoint")
    @classmethod
    def _endpoint_is_a_web_url(cls, endpoint: str) -> str:
        if not _ENDPOINT.fullmatch(endpoint):
            raise ValueError("endpoint must be an http or https URL")
        return endpoint

    # The error must not repeat the value: a pasted key would end up in logs.
    @field_validator("key_variable")
    @classmethod
    def _key_variable_is_a_variable_name(cls, name: str | None) -> str | None:
        if name is not None and not _VARIABLE_NAME.fullmatch(name):
            raise ValueError(
                "key_variable must be the name of an environment variable, "
                "such as EXAMPLE_API_KEY, not a key"
            )
        return name

    @model_validator(mode="after")
    def _only_cloud_profiles_have_a_key(self) -> Self:
        if self.location == "cloud" and self.key_variable is None:
            raise ValueError("a cloud profile needs a key_variable")
        if self.location == "local" and self.key_variable is not None:
            raise ValueError("a local profile must not have a key_variable")
        return self


def parse_profile(source: str, name: str) -> ProviderProfile:
    try:
        raw = load_yaml(source)
    except yaml.YAMLError as error:
        raise ProviderProfileError(f"{name}: not valid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise ProviderProfileError(f"{name}: the top level must be a mapping")
    try:
        return ProviderProfile.model_validate(raw)
    except ValidationError as error:
        raise ProviderProfileError(f"{name}: {format_validation_error(error)}") from error
