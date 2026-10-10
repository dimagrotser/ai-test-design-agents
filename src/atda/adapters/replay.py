import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from atda.ports.llm import LLMClient, LLMRequest, LLMResponse

_HINT_LENGTH = 80


class FixtureError(ValueError):
    pass


class MissingFixture(LookupError):
    pass


def _request_body(request: LLMRequest) -> dict[str, object]:
    return {
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "json_schema": request.json_schema,
        "temperature": request.temperature,
        "seed": request.seed,
        "num_ctx": request.num_ctx,
    }


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# The model is not part of LLMRequest, it belongs to the client, so the caller passes it in.
# An unset seed or context size is JSON null, which keeps the key stable for providers
# that take neither.
def fixture_key(request: LLMRequest, model: str) -> str:
    canonical = _canonical({"model": model, **_request_body(request)})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FixtureStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, request: LLMRequest, model: str, response: LLMResponse) -> str:
        key = fixture_key(request, model)
        # Only the model, the request body and the response body are stored. Headers and
        # keys never reach this class: it sits behind the LLMClient port.
        fixture = {
            "model": model,
            "request": _request_body(request),
            "response": response.model_dump(mode="json"),
        }
        self._directory.mkdir(parents=True, exist_ok=True)
        text = json.dumps(fixture, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        (self._directory / f"{key}.json").write_text(text, encoding="utf-8", newline="\n")
        return key

    def load(self, key: str) -> LLMResponse | None:
        path = self._directory / f"{key}.json"
        if not path.is_file():
            return None
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse.model_validate(stored["response"])
        except (ValueError, KeyError, TypeError, ValidationError) as error:
            raise FixtureError(f"{path}: not a valid fixture: {error}") from None


class ReplayClient(LLMClient):
    def __init__(self, store: FixtureStore, model: str) -> None:
        self._store = store
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        key = fixture_key(request, self._model)
        response = self._store.load(key)
        if response is None:
            hint = " ".join(request.messages[-1].content.split())[:_HINT_LENGTH]
            raise MissingFixture(
                f"no recorded response for key {key} (model {self._model}); the prompt or the "
                f"settings changed since the recording. Last message starts with: {hint!r}"
            )
        return response
