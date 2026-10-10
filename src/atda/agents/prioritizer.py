from collections import Counter
from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

from atda.ports.llm import LLMClient, LLMRequest, Message
from atda.prompts import load_prompt
from atda.schemas.requirements import Analysis
from atda.schemas.risk import Risk, Score
from atda.schemas.story import Story
from atda.structured_generation import Generated, generate


class RiskScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str
    likelihood: Score
    impact: Score


class PrioritizerReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    scores: tuple[RiskScore, ...]

    @model_validator(mode="after")
    def _one_score_for_every_requirement(self, info: ValidationInfo) -> Self:
        if info.context is None:
            raise ValueError("validation context with requirement_ids is required")
        known: tuple[str, ...] = info.context["requirement_ids"]
        if problems := score_problems(self.scores, known):
            raise ValueError("; ".join(problems))
        return self


def score_problems(scores: Sequence[RiskScore], known: Sequence[str]) -> list[str]:
    given = Counter(score.requirement_id for score in scores)
    problems = []
    if unknown := [i for i in given if i not in known]:
        problems.append(
            f"unknown requirement id {', '.join(unknown)}; known ids: {', '.join(known)}"
        )
    if repeated := [i for i, count in given.items() if count > 1]:
        problems.append(f"scored more than once: {', '.join(repeated)}")
    if missing := [i for i in known if i not in given]:
        problems.append(f"no score for {', '.join(missing)}")
    return problems


def prioritize(
    client: LLMClient,
    story: Story,
    analysis: Analysis,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[Analysis]:
    request = LLMRequest(
        messages=(
            Message(role="system", content=load_prompt("risk_prioritizer")),
            Message(role="user", content=_render(story, analysis)),
        ),
        json_schema=PrioritizerReply.model_json_schema(),
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
    )
    context: dict[str, object] = {"requirement_ids": tuple(r.id for r in analysis.requirements)}
    generated = generate(client, request, PrioritizerReply, max_attempts, context)
    risks = {
        score.requirement_id: Risk(likelihood=score.likelihood, impact=score.impact)
        for score in generated.value.scores
    }
    rated = Analysis(
        requirements=tuple(
            requirement.model_copy(update={"risk": risks[requirement.id]})
            for requirement in analysis.requirements
        ),
        gaps=analysis.gaps,
    )
    return Generated(
        value=rated,
        attempts=generated.attempts,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
    )


def _render(story: Story, analysis: Analysis) -> str:
    acs = {ac.id: ac.text for ac in story.acceptance_criteria}
    lines = ["Requirements:"]
    for requirement in analysis.requirements:
        ac = f"{requirement.ac_id}: {acs.get(requirement.ac_id, '')}"
        lines.append(f"- {requirement.id} (from {ac}): {requirement.text}")
    if analysis.gaps:
        lines += ["", "Gaps:"]
        lines += [f"- {gap.ac_id or 'Story'}: {gap.text}" for gap in analysis.gaps]
    else:
        lines += ["", "Gaps: none"]
    return "\n".join(lines)
