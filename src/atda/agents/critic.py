from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

from atda.ports.llm import LLMClient, LLMRequest, Message
from atda.prompts import load_prompt
from atda.report import render_markdown
from atda.schemas.findings import SEMANTIC_TYPES, Finding
from atda.schemas.story import Story
from atda.schemas.test_design import TestDesign
from atda.structured_generation import Generated, generate


class CriticReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    findings: tuple[Finding, ...]

    @model_validator(mode="after")
    def _only_semantic_findings_about_known_ids(self, info: ValidationInfo) -> Self:
        if info.context is None:
            raise ValueError("validation context with known_ids is required")
        known: tuple[str, ...] = info.context["known_ids"]
        problems = []
        for number, found in enumerate(self.findings, start=1):
            if found.type not in SEMANTIC_TYPES:
                problems.append(
                    f"finding {number}: type must be wrong_technique or "
                    f"vague_expected_result, got {found.type.value}"
                )
            if not found.references:
                problems.append(f"finding {number}: no reference")
            if unknown := [r for r in found.references if r not in known]:
                problems.append(
                    f"finding {number}: unknown reference {', '.join(unknown)}; "
                    f"known ids: {', '.join(known)}"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return self


def critique(
    client: LLMClient,
    story: Story,
    design: TestDesign,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
) -> Generated[CriticReport]:
    request = LLMRequest(
        messages=(
            Message(role="system", content=load_prompt("critic")),
            Message(role="user", content=render_markdown(story, design)),
        ),
        json_schema=CriticReport.model_json_schema(),
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
    )
    known_ids = tuple([case.id for case in design.test_cases] + [r.id for r in design.requirements])
    return generate(client, request, CriticReport, max_attempts, {"known_ids": known_ids})
