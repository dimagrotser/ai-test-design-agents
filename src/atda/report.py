import json
from collections.abc import Sequence

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.scalar import Scalar
from atda.schemas.story import Story
from atda.schemas.test_design import TestDesign


def render_json(design: TestDesign) -> str:
    return design.model_dump_json(indent=2) + "\n"


def render_markdown(story: Story, design: TestDesign) -> str:
    sections = [
        f"# Test design {story.id}: {story.title}",
        _requirements(design),
        _gaps(design),
        _test_cases(design),
        _traceability(story, design),
        _checks(design),
    ]
    return "\n\n".join(sections) + "\n"


def _requirements(design: TestDesign) -> str:
    rows = [[r.id, r.ac_id, r.text] for r in design.requirements]
    return _section("Requirements", _table(["Id", "AC", "Requirement"], rows))


def _gaps(design: TestDesign) -> str:
    bullets = [f"- {gap.ac_id or 'Story'}: {_line(gap.text)}" for gap in design.gaps]
    return _section("Gaps", "\n".join(bullets))


def _test_cases(design: TestDesign) -> str:
    rows = [
        [
            case.id,
            case.technique.value,
            ", ".join(f"{name}={_scalar(value)}" for name, value in case.overrides.items())
            or "Nominal input",
            _outcome(case.expected),
            ", ".join(case.requirement_ids),
            ", ".join(case.ac_ids),
            case.rationale,
        ]
        for case in design.test_cases
    ]
    header = ["Id", "Technique", "Input", "Expected", "Requirements", "ACs", "Rationale"]
    return _section("Test cases", _table(header, rows))


def _traceability(story: Story, design: TestDesign) -> str:
    rows: list[list[str]] = []
    for ac in story.acceptance_criteria:
        requirements = [r for r in design.requirements if r.ac_id == ac.id]
        label = f"{ac.id}: {ac.text}"
        if not requirements:
            rows.append([label, "no requirement", "uncovered"])
        for requirement in requirements:
            case_ids = [c.id for c in design.test_cases if requirement.id in c.requirement_ids]
            rows.append([label, requirement.id, ", ".join(case_ids) or "uncovered"])
    return "## Traceability\n\n" + _table(["AC", "Requirement", "Test cases"], rows)


def _checks(design: TestDesign) -> str:
    contradictions = "; ".join(", ".join(c.case_ids) for c in design.contradictions) or "none"
    return (
        "## Checks\n\n"
        f"- Duplicate ratio before merging: {design.duplicate_ratio:.2f}\n"
        f"- Contradictions: {contradictions}"
    )


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body or 'None.'}"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    lines = [_row(header), _row(["---"] * len(header))] + [_row(row) for row in rows]
    return "\n".join(lines)


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(_cell(cell) for cell in cells) + " |"


def _cell(text: str) -> str:
    return _line(text.replace("|", "\\|"))


def _line(text: str) -> str:
    return " ".join(text.split())


def _outcome(outcome: ExpectedOutcome) -> str:
    text = outcome.status
    if outcome.outcome_keys:
        text += f" ({', '.join(outcome.outcome_keys)})"
    if outcome.values:
        text += " " + json.dumps(outcome.values, sort_keys=True)
    return text


def _scalar(value: Scalar) -> str:
    return value if isinstance(value, str) else json.dumps(value)
