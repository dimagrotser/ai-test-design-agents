import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from atda.expansion import expand
from atda.ports.llm import LLMClient, LLMRequest, Message
from atda.prompts import load_prompt
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Analysis
from atda.schemas.story import Story
from atda.schemas.test_condition import BvaCondition, TestCondition
from atda.schemas.test_context import TestContext
from atda.schemas.test_design import TestDesign
from atda.structured_generation import Generated, generate


@dataclass(frozen=True)
class DesignFacts:
    """What a reply is checked against: the Story, the requirements and the Test Context."""

    ac_of: Mapping[str, tuple[str, str]]
    input_names: tuple[str, ...]
    statuses: tuple[str, ...]
    outcome_keys: tuple[str, ...]


class DesignerReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    conditions: tuple[TestCondition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _conditions_fit_the_story(self, info: ValidationInfo) -> Self:
        if info.context is None:
            raise ValueError("validation context with facts is required")
        facts: DesignFacts = info.context["facts"]
        problems = [
            problem
            for number, condition in enumerate(self.conditions, start=1)
            for problem in _problems(condition, number, facts)
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return self


def design_tests(
    client: LLMClient,
    story: Story,
    analysis: Analysis,
    context: TestContext,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[TestDesign]:
    acs = {ac.id: ac.text for ac in story.acceptance_criteria}
    facts = DesignFacts(
        ac_of={r.id: (r.ac_id, acs[r.ac_id]) for r in analysis.requirements},
        input_names=tuple(context.nominal_input),
        statuses=context.statuses,
        outcome_keys=context.outcome_keys,
    )
    request = LLMRequest(
        messages=(
            Message(role="system", content=load_prompt("test_designer")),
            Message(role="user", content=_render(analysis, context, facts)),
        ),
        json_schema=DesignerReply.model_json_schema(),
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
    )
    generated = generate(client, request, DesignerReply, max_attempts, {"facts": facts})
    design = TestDesign(
        story_id=story.id,
        requirements=analysis.requirements,
        gaps=analysis.gaps,
        test_cases=expand(generated.value.conditions, analysis.requirements, context.nominal_input),
    )
    return Generated(
        value=design,
        attempts=generated.attempts,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
    )


def _problems(condition: TestCondition, number: int, facts: DesignFacts) -> Iterator[str]:
    label = f"condition {number} ({condition.technique.value} on {condition.input_name})"
    if condition.requirement_id not in facts.ac_of:
        known = ", ".join(facts.ac_of)
        yield f"{label}: unknown requirement id {condition.requirement_id}; known ids: {known}"
    else:
        ac_id, ac_text = facts.ac_of[condition.requirement_id]
        if _collapse(condition.evidence) not in _collapse(ac_text):
            yield (
                f"{label}: evidence {condition.evidence!r} does not occur in the text of "
                f"{ac_id}: {ac_text!r}"
            )
    if condition.input_name not in facts.input_names:
        known = ", ".join(facts.input_names)
        yield f"{label}: input {condition.input_name} is not in the Nominal Input; known: {known}"
    for where, outcome in _outcomes(condition):
        if outcome.status not in facts.statuses:
            known = ", ".join(facts.statuses)
            yield f"{label}: {where}: unknown status {outcome.status}; known statuses: {known}"
        for key in outcome.outcome_keys:
            if key not in facts.outcome_keys:
                known = ", ".join(facts.outcome_keys)
                yield f"{label}: {where}: unknown Outcome Key {key}; known keys: {known}"


def _outcomes(condition: TestCondition) -> list[tuple[str, ExpectedOutcome]]:
    if isinstance(condition, BvaCondition):
        return [
            ("outcome_if_true", condition.outcome_if_true),
            ("outcome_if_false", condition.outcome_if_false),
        ]
    return [(f"class {c.name}", c.outcome) for c in condition.classes]


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _render(analysis: Analysis, context: TestContext, facts: DesignFacts) -> str:
    lines = [f"Target: {context.target}", "", "Requirements:"]
    for requirement in analysis.requirements:
        ac_id, ac_text = facts.ac_of[requirement.id]
        lines.append(f"- {requirement.id} (from {ac_id}: {ac_text}): {requirement.text}")
    lines += ["", "Inputs with example values:"]
    lines += [f"- {name}: {json.dumps(value)}" for name, value in context.nominal_input.items()]
    lines += [
        "",
        f"Statuses: {', '.join(context.statuses)}",
        f"Outcome Keys: {', '.join(context.outcome_keys)}",
    ]
    return "\n".join(lines)
