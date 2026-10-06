from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from atda.ports.llm import LLMClient, LLMRequest, Message
from atda.schemas.validation import format_validation_error

# Prompt files arrive with the first agent, so the wording lives here until then.
RETRY_MESSAGE = (
    "Your previous answer was not valid: {error}\nAnswer again with only the corrected JSON."
)


@dataclass(frozen=True)
class FailedAttempt:
    raw: str
    error: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Generated[T: BaseModel]:
    value: T
    attempts: int
    input_tokens: int
    output_tokens: int


class StructuredGenerationError(Exception):
    def __init__(self, attempts: tuple[FailedAttempt, ...]) -> None:
        self.attempts = attempts
        super().__init__(
            f"no valid answer after {len(attempts)} attempts, last error: {attempts[-1].error}"
        )

    @property
    def input_tokens(self) -> int:
        return sum(a.input_tokens for a in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(a.output_tokens for a in self.attempts)


def generate[T: BaseModel](
    client: LLMClient,
    request: LLMRequest,
    model_type: type[T],
    max_attempts: int = 3,
    context: dict[str, object] | None = None,
) -> Generated[T]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    failures: list[FailedAttempt] = []
    current = request
    for attempt in range(1, max_attempts + 1):
        response = client.complete(current)
        try:
            value = model_type.model_validate_json(response.text, context=context)
        except ValidationError as error:
            problem = format_validation_error(error)
            failures.append(
                FailedAttempt(response.text, problem, response.input_tokens, response.output_tokens)
            )
            current = current.model_copy(
                update={
                    "messages": (
                        *current.messages,
                        Message(role="assistant", content=response.text),
                        Message(role="user", content=RETRY_MESSAGE.format(error=problem)),
                    )
                }
            )
            continue
        return Generated(
            value=value,
            attempts=attempt,
            input_tokens=response.input_tokens + sum(f.input_tokens for f in failures),
            output_tokens=response.output_tokens + sum(f.output_tokens for f in failures),
        )
    raise StructuredGenerationError(tuple(failures))
