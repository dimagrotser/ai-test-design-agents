from collections import deque
from collections.abc import Sequence

from atda.ports.llm import LLMClient, LLMRequest, LLMResponse


class FakeLLMClient(LLMClient):
    def __init__(self, responses: Sequence[str | LLMResponse]) -> None:
        self._responses = deque(
            LLMResponse(text=r, input_tokens=0, output_tokens=0) if isinstance(r, str) else r
            for r in responses
        )
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("FakeLLMClient has no scripted response left")
        return self._responses.popleft()
