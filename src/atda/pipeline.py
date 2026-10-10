from atda.agents.analyst import analyze
from atda.agents.designer import design_tests
from atda.agents.prioritizer import prioritize
from atda.ports.llm import LLMClient
from atda.priority import with_priorities
from atda.refinement import refine_design
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
    critic: bool = False,
) -> Generated[TestDesign]:
    analysis = analyze(
        client,
        story,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        max_attempts=max_attempts,
    )
    design_step = refine_design if critic else design_tests
    design = design_step(
        client,
        story,
        analysis.value,
        context,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        max_attempts=max_attempts,
    )
    rated = prioritize(
        client,
        story,
        analysis.value,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        max_attempts=max_attempts,
    )
    prioritized = with_priorities(
        design.value.model_copy(update={"requirements": rated.value.requirements})
    )
    return Generated(
        value=prioritized,
        attempts=analysis.attempts + design.attempts + rated.attempts,
        input_tokens=analysis.input_tokens + design.input_tokens + rated.input_tokens,
        output_tokens=analysis.output_tokens + design.output_tokens + rated.output_tokens,
    )
