from enum import StrEnum

from atda.agents.single_prompt import single_prompt
from atda.pipeline import run_pipeline
from atda.ports.llm import LLMClient
from atda.schemas.story import Story
from atda.schemas.test_context import TestContext
from atda.schemas.test_design import TestDesign
from atda.structured_generation import Generated


class Variant(StrEnum):
    SINGLE_PROMPT = "single-prompt"
    PIPELINE = "pipeline"
    PIPELINE_WITH_CRITIC = "pipeline-with-critic"


def run_variant(
    variant: Variant,
    client: LLMClient,
    story: Story,
    context: TestContext,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[TestDesign]:
    if variant is Variant.SINGLE_PROMPT:
        return single_prompt(
            client,
            story,
            context,
            temperature=temperature,
            seed=seed,
            num_ctx=num_ctx,
            max_attempts=max_attempts,
        )
    return run_pipeline(
        client,
        story,
        context,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        max_attempts=max_attempts,
        critic=variant is Variant.PIPELINE_WITH_CRITIC,
    )
