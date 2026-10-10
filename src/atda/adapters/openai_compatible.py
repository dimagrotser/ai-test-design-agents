import os

from atda.adapters.errors import IncompleteResponse, MalformedResponse, MissingApiKey
from atda.adapters.http import Transport, post_json
from atda.ports.llm import LLMClient, LLMRequest, LLMResponse


# Untested against any real server until a profile has been run with a key.
# `endpoint` is the full chat completions URL. The API has no context size option, so
# `num_ctx` is ignored. The schema is sent in best-effort mode (`strict: false`): strict mode
# needs every property required, and the core validates the reply with Pydantic anyway.
class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        model: str,
        *,
        endpoint: str,
        key_variable: str,
        timeout: float = 120.0,
        transport: Transport = post_json,
    ) -> None:
        key = os.environ.get(key_variable)
        if not key:
            raise MissingApiKey(f"environment variable {key_variable} is not set")
        self._model = model
        self._endpoint = endpoint
        self._key = key
        self._timeout = timeout
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenAICompatibleClient(model={self._model!r}, endpoint={self._endpoint!r})"

    def complete(self, request: LLMRequest) -> LLMResponse:
        payload: dict[str, object] = {
            "model": self._model,
            "temperature": request.temperature,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "reply", "strict": False, "schema": request.json_schema},
            }
        body = self._transport(
            self._endpoint,
            payload,
            {"Authorization": f"Bearer {self._key}"},
            timeout=self._timeout,
        )
        choice = _first_choice(body)
        finish_reason = str(choice.get("finish_reason"))
        if finish_reason != "stop":
            raise IncompleteResponse(finish_reason)
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise MalformedResponse("the response has no message content")
        usage = body.get("usage")
        if not isinstance(usage, dict):
            raise MalformedResponse("the response has no usage, so token counts are unknown")
        try:
            input_tokens, output_tokens = (
                int(usage["prompt_tokens"]),
                int(usage["completion_tokens"]),
            )
        except (KeyError, TypeError, ValueError):
            raise MalformedResponse(
                "the usage has no prompt_tokens and completion_tokens"
            ) from None
        return LLMResponse(text=content, input_tokens=input_tokens, output_tokens=output_tokens)


def _first_choice(body: dict[str, object]) -> dict[str, object]:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise MalformedResponse("the response has no choices")
    first: dict[str, object] = choices[0]
    return first
