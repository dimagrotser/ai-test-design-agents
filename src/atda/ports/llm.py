from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    messages: tuple[Message, ...]
    json_schema: dict[str, object] | None = None
    temperature: float
    seed: int | None = None
    num_ctx: int | None = None


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...
