from collections.abc import Sequence
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    model_validator,
)

from atda.ports.llm import LLMClient, LLMRequest, Message
from atda.prompts import load_prompt
from atda.schemas.requirements import Analysis, Gap, Requirement
from atda.schemas.story import Story
from atda.structured_generation import Generated, generate

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExtractedRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    ac_id: str
    text: Text


class AnalystReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirements: tuple[ExtractedRequirement, ...] = Field(min_length=1)
    gaps: tuple[Gap, ...] = ()

    @model_validator(mode="after")
    def _ac_ids_exist(self, info: ValidationInfo) -> Self:
        if info.context is None:
            raise ValueError("validation context with ac_ids is required")
        known: tuple[str, ...] = info.context["ac_ids"]
        cited = [r.ac_id for r in self.requirements] + [g.ac_id for g in self.gaps if g.ac_id]
        if problems := ac_id_problems(cited, known):
            raise ValueError("; ".join(problems))
        return self


def ac_id_problems(cited: Sequence[str], known: Sequence[str]) -> list[str]:
    unknown = list(dict.fromkeys(ac_id for ac_id in cited if ac_id not in known))
    if not unknown:
        return []
    return [f"unknown AC id {', '.join(unknown)}; known ids: {', '.join(known)}"]


def analyze(
    client: LLMClient,
    story: Story,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[Analysis]:
    request = LLMRequest(
        messages=(
            Message(role="system", content=load_prompt("requirements_analyst")),
            Message(role="user", content=render_story(story)),
        ),
        json_schema=AnalystReply.model_json_schema(),
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
    )
    context: dict[str, object] = {"ac_ids": tuple(ac.id for ac in story.acceptance_criteria)}
    generated = generate(client, request, AnalystReply, max_attempts, context)
    analysis = Analysis(
        requirements=tuple(
            Requirement(id=f"{story.id}.R{n}", ac_id=r.ac_id, text=r.text)
            for n, r in enumerate(generated.value.requirements, start=1)
        ),
        gaps=generated.value.gaps,
    )
    return Generated(
        value=analysis,
        attempts=generated.attempts,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
    )


def render_story(story: Story) -> str:
    lines = [f"Story {story.id}: {story.title}", ""]
    if story.text:
        lines += [story.text, ""]
    lines.append("Acceptance criteria:")
    lines += [f"- {ac.id}: {ac.text}" for ac in story.acceptance_criteria]
    return "\n".join(lines)
