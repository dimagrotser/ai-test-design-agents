from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from atda.agents.analyst import ExtractedRequirement, ac_id_problems, render_story
from atda.agents.designer import DesignFacts, assemble_design, condition_problems, render_context
from atda.agents.prioritizer import RiskScore, score_problems
from atda.ports.llm import LLMClient, LLMRequest, Message
from atda.priority import with_priorities
from atda.prompts import load_prompt
from atda.schemas.requirements import Analysis, Gap, Requirement
from atda.schemas.risk import Risk
from atda.schemas.story import Story
from atda.schemas.test_condition import TestCondition
from atda.schemas.test_context import TestContext
from atda.schemas.test_design import TestDesign
from atda.structured_generation import Generated, generate


def requirement_ids(story: Story, count: int) -> tuple[str, ...]:
    return tuple(f"{story.id}.R{n}" for n in range(1, count + 1))


class SinglePromptReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirements: tuple[ExtractedRequirement, ...] = Field(min_length=1)
    gaps: tuple[Gap, ...] = ()
    conditions: tuple[TestCondition, ...] = Field(min_length=1)
    scores: tuple[RiskScore, ...]

    @model_validator(mode="after")
    def _everything_fits_the_story_and_the_test_context(self, info: ValidationInfo) -> Self:
        if info.context is None:
            raise ValueError("validation context with story and test_context is required")
        story: Story = info.context["story"]
        context: TestContext = info.context["test_context"]
        acs = {ac.id: ac.text for ac in story.acceptance_criteria}
        cited = [r.ac_id for r in self.requirements] + [g.ac_id for g in self.gaps if g.ac_id]
        problems = ac_id_problems(cited, tuple(acs))
        ids = requirement_ids(story, len(self.requirements))
        if not problems:
            facts = DesignFacts(
                ac_of={
                    i: (r.ac_id, acs[r.ac_id]) for i, r in zip(ids, self.requirements, strict=True)
                },
                nominal_input=context.nominal_input,
                statuses=context.statuses,
                outcome_keys=context.outcome_keys,
            )
            problems = condition_problems(self.conditions, facts)
        problems += score_problems(self.scores, ids)
        if problems:
            raise ValueError("; ".join(problems))
        return self


def single_prompt(
    client: LLMClient,
    story: Story,
    context: TestContext,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[TestDesign]:
    request = LLMRequest(
        messages=(
            Message(role="system", content=load_prompt("single_prompt")),
            Message(role="user", content=f"{render_story(story)}\n\n{render_context(context)}"),
        ),
        json_schema=SinglePromptReply.model_json_schema(),
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
    )
    validation: dict[str, object] = {"story": story, "test_context": context}
    generated = generate(client, request, SinglePromptReply, max_attempts, validation)
    reply = generated.value
    risks = {s.requirement_id: Risk(likelihood=s.likelihood, impact=s.impact) for s in reply.scores}
    ids = requirement_ids(story, len(reply.requirements))
    analysis = Analysis(
        requirements=tuple(
            Requirement(id=i, ac_id=r.ac_id, text=r.text, risk=risks[i])
            for i, r in zip(ids, reply.requirements, strict=True)
        ),
        gaps=reply.gaps,
    )
    design = assemble_design(story.id, analysis, reply.conditions, context.nominal_input)
    return Generated(
        value=with_priorities(design),
        attempts=generated.attempts,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
    )
