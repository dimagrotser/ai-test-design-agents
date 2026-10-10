from atda.agents.analyst import analyze
from atda.agents.designer import design_tests
from atda.ports.llm import LLMClient
from atda.schemas.story import Story
from atda.schemas.test_context import TestContext
from atda.schemas.test_design import TestDesign
from atda.structured_generation import Generated


def run_pipeline(
    client: LLMClient,
    story: Story,
    context: TestContext,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[TestDesign]:
    analysis = analyze(
        client,
        story,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        max_attempts=max_attempts,
    )
    design = design_tests(
        client,
        story,
        analysis.value,
        context,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        max_attempts=max_attempts,
    )
    return Generated(
        value=design.value,
        attempts=analysis.attempts + design.attempts,
        input_tokens=analysis.input_tokens + design.input_tokens,
        output_tokens=analysis.output_tokens + design.output_tokens,
    )
