import pytest
from pydantic import BaseModel, ValidationInfo, field_validator

from atda.adapters.fake import FakeLLMClient
from atda.ports.llm import LLMRequest, LLMResponse, Message
from atda.structured_generation import StructuredGenerationError, generate

GOOD = '{"answer": "ok", "confidence": 2}'
MISSING_FIELD = '{"answer": "ok"}'


class Answer(BaseModel):
    answer: str
    confidence: int


class Tagged(BaseModel):
    tag: str

    @field_validator("tag")
    @classmethod
    def _tag_is_allowed(cls, tag: str, info: ValidationInfo) -> str:
        allowed = info.context["allowed"] if info.context else ()
        if tag not in allowed:
            raise ValueError(f"unknown tag {tag}")
        return tag


def ask() -> LLMRequest:
    return LLMRequest(
        messages=(Message(role="system", content="Be brief."), Message(role="user", content="Hi")),
        json_schema={"type": "object"},
        temperature=0.3,
        seed=7,
        num_ctx=4096,
    )


def reply(text: str, input_tokens: int = 0, output_tokens: int = 0) -> LLMResponse:
    return LLMResponse(text=text, input_tokens=input_tokens, output_tokens=output_tokens)


def test_a_valid_first_answer_is_returned_after_one_attempt() -> None:
    client = FakeLLMClient([GOOD])

    result = generate(client, ask(), Answer)

    assert result.value == Answer(answer="ok", confidence=2)
    assert result.attempts == 1
    assert len(client.requests) == 1


def test_a_schema_error_is_retried_with_the_error_text() -> None:
    client = FakeLLMClient([MISSING_FIELD, GOOD])

    result = generate(client, ask(), Answer)

    retry = client.requests[1].messages
    assert result.attempts == 2
    assert retry[:2] == ask().messages
    assert retry[2] == Message(role="assistant", content=MISSING_FIELD)
    assert retry[3].role == "user"
    assert "confidence" in retry[3].content
    assert "Field required" in retry[3].content


def test_an_answer_that_is_not_json_counts_as_a_failed_attempt() -> None:
    client = FakeLLMClient(["not json at all", GOOD])

    result = generate(client, ask(), Answer)

    assert result.attempts == 2
    assert "Invalid JSON" in client.requests[1].messages[-1].content


def test_after_the_last_attempt_the_exception_holds_every_attempt_in_order() -> None:
    answers = ["not json", MISSING_FIELD, '{"answer": 1, "confidence": 2}']
    client = FakeLLMClient(answers)

    with pytest.raises(StructuredGenerationError) as failure:
        generate(client, ask(), Answer, max_attempts=3)

    attempts = failure.value.attempts
    assert [a.raw for a in attempts] == answers
    assert "Invalid JSON" in attempts[0].error
    assert "confidence" in attempts[1].error
    assert "answer" in attempts[2].error
    assert len(client.requests) == 3
    assert "3 attempts" in str(failure.value)


def test_tokens_are_summed_over_attempts() -> None:
    client = FakeLLMClient([reply(MISSING_FIELD, 10, 5), reply(GOOD, 12, 6)])

    result = generate(client, ask(), Answer)

    assert (result.input_tokens, result.output_tokens) == (22, 11)


def test_tokens_are_summed_on_the_exception_too() -> None:
    client = FakeLLMClient([reply("bad", 1, 2), reply("bad", 3, 4)])

    with pytest.raises(StructuredGenerationError) as failure:
        generate(client, ask(), Answer, max_attempts=2)

    assert (failure.value.input_tokens, failure.value.output_tokens) == (4, 6)


def test_failed_answers_accumulate_and_the_request_settings_stay_the_same() -> None:
    request = ask()
    client = FakeLLMClient(["first bad", "second bad", GOOD])

    generate(client, request, Answer)

    third = client.requests[2]
    assert len(third.messages) == 2 + 2 * 2
    assert [m.content for m in third.messages if m.role == "assistant"] == [
        "first bad",
        "second bad",
    ]
    for sent in client.requests:
        assert (sent.temperature, sent.seed, sent.num_ctx) == (0.3, 7, 4096)
        assert sent.json_schema == {"type": "object"}
    assert request == ask()


def test_at_least_one_attempt_is_required() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        generate(FakeLLMClient([GOOD]), ask(), Answer, max_attempts=0)


def test_the_validation_context_reaches_the_model_validators() -> None:
    client = FakeLLMClient(['{"tag": "x"}', '{"tag": "a"}'])

    result = generate(client, ask(), Tagged, context={"allowed": ("a", "b")})

    assert result.value.tag == "a"
    assert result.attempts == 2
    assert "unknown tag x" in client.requests[1].messages[-1].content
