from dataclasses import dataclass

from atda.agents.critic import CriticReport, critique
from atda.agents.designer import Feedback, design_tests
from atda.findings import deterministic_findings
from atda.lexicon import Lexicon, load_lexicon
from atda.ports.llm import LLMClient
from atda.schemas.findings import Finding, Severity
from atda.schemas.requirements import Analysis
from atda.schemas.story import Story
from atda.schemas.test_context import TestContext
from atda.schemas.test_design import TestDesign
from atda.structured_generation import Generated


@dataclass
class _Usage:
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, call: Generated[TestDesign] | Generated[CriticReport]) -> None:
        self.attempts += call.attempts
        self.input_tokens += call.input_tokens
        self.output_tokens += call.output_tokens


def refine_design(
    client: LLMClient,
    story: Story,
    analysis: Analysis,
    context: TestContext,
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    num_ctx: int | None = None,
    max_attempts: int = 3,
    max_rounds: int = 2,
    lexicon: Lexicon | None = None,
) -> Generated[TestDesign]:
    """Design, review, and send blocking Findings back to the Designer for at most max_rounds.

    The Analyst is not part of the loop: the Requirements come in as an argument and the
    Designer keeps them, so their ids cannot change.
    """
    usage = _Usage()
    rules = lexicon if lexicon is not None else load_lexicon()

    def design(feedback: Feedback | None) -> TestDesign:
        generated = design_tests(
            client,
            story,
            analysis,
            context,
            temperature=temperature,
            seed=seed,
            num_ctx=num_ctx,
            max_attempts=max_attempts,
            feedback=feedback,
        )
        usage.add(generated)
        return generated.value

    def review(candidate: TestDesign) -> tuple[Finding, ...]:
        report = critique(
            client,
            story,
            candidate,
            temperature=temperature,
            seed=seed,
            num_ctx=num_ctx,
            max_attempts=max_attempts,
        )
        usage.add(report)
        found = deterministic_findings(story, candidate, context.nominal_input, rules)
        return (*found, *report.value.findings)

    current = design(None)
    findings = review(current)
    for _ in range(max_rounds):
        blocking = tuple(f for f in findings if f.severity is Severity.BLOCKING)
        if not blocking:
            break
        current = design(Feedback(conditions=current.conditions, findings=blocking))
        findings = review(current)
    return Generated(
        value=current.model_copy(update={"findings": findings}),
        attempts=usage.attempts,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
