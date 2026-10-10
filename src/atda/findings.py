from collections.abc import Iterator, Mapping

from atda.lexicon import Lexicon, implied_operators
from atda.merge import InputKey, input_key, outcome_key
from atda.schemas.findings import Finding, FindingType, finding
from atda.schemas.scalar import Scalar
from atda.schemas.story import Story
from atda.schemas.test_condition import BvaCondition
from atda.schemas.test_design import TestDesign


def deterministic_findings(
    story: Story,
    design: TestDesign,
    nominal_input: Mapping[str, Scalar],
    lexicon: Lexicon,
) -> tuple[Finding, ...]:
    return (
        *_missing_coverage(story, design),
        *_untraceable(story, design),
        *_duplicates(design, nominal_input),
        *_contradictions(design),
        *_operator_mismatches(design, lexicon),
    )


def _missing_coverage(story: Story, design: TestDesign) -> Iterator[Finding]:
    traced_acs = {ac for case in design.test_cases for ac in case.ac_ids}
    traced_requirements = {r for case in design.test_cases for r in case.requirement_ids}
    acs_with_requirements = {requirement.ac_id for requirement in design.requirements}
    for ac in story.acceptance_criteria:
        if ac.id in traced_acs:
            continue
        message = (
            f"{ac.id} has no Test Case"
            if ac.id in acs_with_requirements
            else f"{ac.id} has no Requirement and no Test Case"
        )
        yield finding(FindingType.MISSING_COVERAGE, (ac.id,), message)
    for requirement in design.requirements:
        if requirement.id not in traced_requirements:
            message = f"{requirement.id} has no Test Case"
            yield finding(FindingType.MISSING_COVERAGE, (requirement.id,), message)


def _untraceable(story: Story, design: TestDesign) -> Iterator[Finding]:
    known_requirements = {requirement.id for requirement in design.requirements}
    known_acs = {ac.id for ac in story.acceptance_criteria}
    for case in design.test_cases:
        problems = []
        if not case.requirement_ids:
            problems.append("no Requirement")
        if not case.ac_ids:
            problems.append("no AC")
        problems += [
            f"unknown Requirement {i}" for i in case.requirement_ids if i not in known_requirements
        ]
        problems += [f"unknown AC {i}" for i in case.ac_ids if i not in known_acs]
        if problems:
            yield finding(FindingType.UNTRACEABLE, (case.id,), f"{case.id}: {'; '.join(problems)}")


def _duplicates(design: TestDesign, nominal_input: Mapping[str, Scalar]) -> Iterator[Finding]:
    first_seen: dict[tuple[InputKey, str], str] = {}
    for case in design.test_cases:
        key = (input_key(nominal_input, case.overrides), outcome_key(case.expected))
        if key in first_seen:
            original = first_seen[key]
            message = f"{case.id} repeats the input and outcome of {original}"
            yield finding(FindingType.DUPLICATE, (original, case.id), message)
        else:
            first_seen[key] = case.id


def _contradictions(design: TestDesign) -> Iterator[Finding]:
    for contradiction in design.contradictions:
        ids = ", ".join(contradiction.case_ids)
        message = f"{ids} have the same input and different outcomes"
        yield finding(FindingType.CONTRADICTION, contradiction.case_ids, message)


def _operator_mismatches(design: TestDesign, lexicon: Lexicon) -> Iterator[Finding]:
    for condition in design.conditions:
        if not isinstance(condition, BvaCondition):
            continue
        implied = implied_operators(condition.evidence, lexicon)
        if implied and condition.operator not in implied:
            suggested = ", ".join(sorted(operator.value for operator in implied))
            message = (
                f"evidence {condition.evidence!r} suggests {suggested}, "
                f"the condition uses {condition.operator.value}"
            )
            yield finding(FindingType.OPERATOR_MISMATCH, (condition.requirement_id,), message)
