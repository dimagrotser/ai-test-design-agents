from pathlib import Path

from atda.report import render_json, render_markdown
from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.requirements import Gap, Requirement
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_condition import Technique
from atda.schemas.test_design import Contradiction, TestCase, TestDesign

GOLDEN = Path(__file__).parent / "golden" / "test-design.md"

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
        AcceptanceCriterion(id="AC-2", text="Transactions from KP, IR or SY are rejected."),
        AcceptanceCriterion(id="AC-3", text="A rejection lists every broken rule."),
        AcceptanceCriterion(id="AC-4", text="Five or more transactions are rejected."),
        AcceptanceCriterion(id="AC-5", text="Nothing else changes."),
    ),
)


def case(
    case_id: str,
    technique: Technique,
    requirements: tuple[str, ...],
    acs: tuple[str, ...],
    overrides: dict[str, str | int | float | bool],
    expected: ExpectedOutcome,
    rationale: str,
) -> TestCase:
    return TestCase(
        id=case_id,
        requirement_ids=requirements,
        ac_ids=acs,
        technique=technique,
        rationale=rationale,
        overrides=overrides,
        expected=expected,
    )


DESIGN = TestDesign(
    story_id="FRAUD-1",
    requirements=(
        Requirement(id="FRAUD-1.R1", ac_id="AC-1", text="An amount over 10000 is rejected."),
        Requirement(
            id="FRAUD-1.R2", ac_id="AC-2", text="Transactions from KP, IR or SY are rejected."
        ),
        Requirement(id="FRAUD-1.R3", ac_id="AC-3", text="Every broken rule is reported."),
        Requirement(id="FRAUD-1.R4", ac_id="AC-4", text="Five or more transactions are rejected."),
    ),
    gaps=(
        Gap(ac_id="AC-1", text="Is 10000 itself rejected?"),
        Gap(text="Which currency is the limit in?"),
    ),
    test_cases=(
        case(
            "TC-1",
            Technique.BVA,
            ("FRAUD-1.R1",),
            ("AC-1",),
            {"amount": "10000.01"},
            ExpectedOutcome(status="rejected", outcome_keys=("amount_limit",)),
            "boundary 10000 of amount (>): just above",
        ),
        case(
            "TC-2",
            Technique.EP,
            ("FRAUD-1.R2", "FRAUD-1.R3"),
            ("AC-2", "AC-3"),
            {"country": "KP"},
            ExpectedOutcome(status="rejected", outcome_keys=("blocked_country",)),
            "class 'blocked' of country: KP; decision table row 3: amount false, country true",
        ),
        case(
            "TC-3",
            Technique.DECISION_TABLE,
            ("FRAUD-1.R3",),
            ("AC-3",),
            {"amount": "10000.01", "country": "KP"},
            ExpectedOutcome(status="rejected", outcome_keys=("amount_limit", "blocked_country")),
            "decision table row 4: amount true, country true",
        ),
        case(
            "TC-4",
            Technique.BVA,
            ("FRAUD-1.R1",),
            ("AC-1",),
            {},
            ExpectedOutcome(status="approved", outcome_keys=(), values={"checked": True}),
            "boundary 10000 of amount (>): just below",
        ),
    ),
    duplicate_ratio=0.25,
    contradictions=(Contradiction(case_ids=("TC-1", "TC-4")),),
)


def test_the_json_loads_back_into_an_equal_test_design() -> None:
    text = render_json(DESIGN)

    assert TestDesign.model_validate_json(text) == DESIGN
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")


def test_rendering_twice_gives_the_same_text() -> None:
    assert render_json(DESIGN) == render_json(DESIGN)
    assert render_markdown(STORY, DESIGN) == render_markdown(STORY, DESIGN)


def test_the_markdown_matches_the_golden_file() -> None:
    assert render_markdown(STORY, DESIGN) == GOLDEN.read_text(encoding="utf-8")


def test_sections_come_in_the_stated_order() -> None:
    text = render_markdown(STORY, DESIGN)

    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Requirements",
        "## Gaps",
        "## Test cases",
        "## Traceability",
        "## Checks",
    ]


def test_an_empty_design_says_so_and_still_lists_every_ac_as_uncovered() -> None:
    empty = TestDesign(story_id="FRAUD-1", requirements=(), gaps=(), test_cases=())

    text = render_markdown(STORY, empty)

    assert "## Gaps\n\nNone.\n" in text
    assert "- Contradictions: none" in text
    assert "- Duplicate ratio before merging: 0.00" in text
    assert text.count("| no requirement | uncovered |") == 5


def test_a_merged_case_is_listed_under_every_requirement_it_traces_to() -> None:
    text = render_markdown(STORY, DESIGN)

    assert "| FRAUD-1.R2 | TC-2 |" in text
    assert "| FRAUD-1.R3 | TC-2, TC-3 |" in text


def test_a_requirement_without_cases_and_an_ac_without_a_requirement_are_uncovered() -> None:
    text = render_markdown(STORY, DESIGN)

    assert "| AC-4: Five or more transactions are rejected. | FRAUD-1.R4 | uncovered |" in text
    assert "| AC-5: Nothing else changes. | no requirement | uncovered |" in text


def test_pipes_and_line_breaks_cannot_break_a_table_cell() -> None:
    design = TestDesign(
        story_id="FRAUD-1",
        requirements=(Requirement(id="FRAUD-1.R1", ac_id="AC-1", text="Either | or\nboth."),),
        gaps=(),
        test_cases=(
            case(
                "TC-1",
                Technique.BVA,
                ("FRAUD-1.R1",),
                ("AC-1",),
                {"note": "a|b"},
                ExpectedOutcome(status="ok", outcome_keys=()),
                "why | because\nreally",
            ),
        ),
    )

    text = render_markdown(STORY, design)

    assert "| FRAUD-1.R1 | AC-1 | Either \\| or both. |" in text
    assert "note=a\\|b" in text
    assert "why \\| because really" in text
