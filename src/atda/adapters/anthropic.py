import os
from collections.abc import Callable, Mapping

from atda.adapters.http import post_json
from atda.ports.llm import LLMClient, LLMRequest, LLMResponse

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# Keywords the structured output endpoint rejects. The full Pydantic model in the core
# still checks them, so a violation comes back as a retry message instead.
_UNSUPPORTED = frozenset(
    {"minimum", "maximum", "multipleOf", "minLength", "maxLength", "maxItems", "discriminator"}
)

Transport = Callable[..., dict[str, object]]


class MissingApiKey(RuntimeError):
    pass


class IncompleteResponse(RuntimeError):
    def __init__(self, stop_reason: str) -> None:
        super().__init__(f"the model stopped with stop_reason {stop_reason!r}")
        self.stop_reason = stop_reason


def strict_schema(schema: Mapping[str, object]) -> dict[str, object]:
    return _strict(schema)  # type: ignore[return-value]


def _strict(node: object) -> object:
    if isinstance(node, list):
        return [_strict(item) for item in node]
    if not isinstance(node, dict):
        return node
    result: dict[str, object] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED or (key == "minItems" and value not in (0, 1)):
            continue
        result["anyOf" if key == "oneOf" else key] = _strict(value)
    if result.get("type") == "object":
        result["additionalProperties"] = False
    return result


# Untested against the real API until the `live` test has been run with a key (ADR 0009).
# The API has no seed and no context size option, so `seed` and `num_ctx` are ignored.
class AnthropicClient(LLMClient):
    def __init__(
        self,
        model: str,
        *,
        endpoint: str = URL,
        key_variable: str = "ANTHROPIC_API_KEY",
        max_tokens: int = 8192,
        timeout: float = 120.0,
        transport: Transport = post_json,
    ) -> None:
        key = os.environ.get(key_variable)
        if not key:
            raise MissingApiKey(f"environment variable {key_variable} is not set")
        self._model = model
        self._endpoint = endpoint
        self._key = key
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._transport = transport

    def __repr__(self) -> str:
        return f"AnthropicClient(model={self._model!r})"

    def complete(self, request: LLMRequest) -> LLMResponse:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        payload: dict[str, object] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": request.temperature,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
                if m.role != "system"
            ],
        }
        if system:
            payload["system"] = system
        if request.json_schema is not None:
            payload["output_config"] = {
                "format": {"type": "json_schema", "schema": strict_schema(request.json_schema)}
            }
        body = self._transport(
            self._endpoint,
            payload,
            {"x-api-key": self._key, "anthropic-version": API_VERSION},
            timeout=self._timeout,
        )
        stop_reason = str(body.get("stop_reason"))
        if stop_reason != "end_turn":
            raise IncompleteResponse(stop_reason)
        usage: dict[str, int] = body["usage"]  # type: ignore[assignment]
        blocks: list[dict[str, str]] = body["content"]  # type: ignore[assignment]
        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        return LLMResponse(
            text=text, input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"]
        )
