from atda.ports.llm import LLMRequest, LLMResponse, Message


def test_request_survives_a_json_round_trip() -> None:
    request = LLMRequest(
        messages=(Message(role="system", content="Be brief."), Message(role="user", content="Hi")),
        json_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        temperature=0.3,
        seed=7,
        num_ctx=16384,
    )

    assert LLMRequest.model_validate_json(request.model_dump_json()) == request


def test_request_needs_only_messages_and_temperature() -> None:
    request = LLMRequest(messages=(Message(role="user", content="Hi"),), temperature=0)

    assert request.json_schema is None
    assert request.seed is None
    assert request.num_ctx is None


def test_response_survives_a_json_round_trip() -> None:
    response = LLMResponse(text='{"answer": "ok"}', input_tokens=12, output_tokens=5)

    assert LLMResponse.model_validate_json(response.model_dump_json()) == response
