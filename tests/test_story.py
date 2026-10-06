import pytest

from atda.schemas.story import AcceptanceCriterion, StoryFormatError, parse_story

FRAUD = """---
id: FRAUD-1
title: Reject risky transactions
---
A transaction is checked against the anti-fraud rules.

## Acceptance criteria

- AC-1: A transaction with an amount over 10 000 is rejected.
- AC-2: Transactions from KP, IR or SY are rejected.
"""


def document(front: str = "id: S-1\ntitle: A story", body: str | None = None) -> str:
    if body is None:
        body = "## Acceptance criteria\n\n- AC-1: Something holds.\n"
    return f"---\n{front}\n---\n{body}"


def test_story_keeps_id_title_text_and_every_criterion() -> None:
    story = parse_story(FRAUD, "fraud.md")

    assert story.id == "FRAUD-1"
    assert story.title == "Reject risky transactions"
    assert story.text == "A transaction is checked against the anti-fraud rules."
    assert story.acceptance_criteria == (
        AcceptanceCriterion(
            id="AC-1", text="A transaction with an amount over 10 000 is rejected."
        ),
        AcceptanceCriterion(id="AC-2", text="Transactions from KP, IR or SY are rejected."),
    )


def test_windows_line_endings_are_accepted() -> None:
    story = parse_story(FRAUD.replace("\n", "\r\n"), "fraud.md")

    assert [c.id for c in story.acceptance_criteria] == ["AC-1", "AC-2"]
    assert "\r" not in story.text


def test_criteria_end_at_the_next_heading_and_stay_out_of_the_text() -> None:
    source = document(
        body=(
            "Intro text.\n\n## Acceptance criteria\n\n- AC-1: First.\n- AC-2: Second.\n\n"
            "## Notes\n\nSome notes.\n"
        )
    )

    story = parse_story(source, "notes.md")

    assert [c.id for c in story.acceptance_criteria] == ["AC-1", "AC-2"]
    assert story.text == "Intro text.\n\n## Notes\n\nSome notes."


def test_yaml_words_that_look_like_booleans_stay_text() -> None:
    story = parse_story(document(front="id: S-1\ntitle: no"), "story.md")

    assert story.title == "no"


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        ("## Acceptance criteria\n\n- AC-1: x\n", "front matter"),
        ("---\nid: S-1\n---\n## Acceptance criteria\n\n- AC-1: x\n", "missing title"),
        (document(front="title: A story"), "missing id"),
        (document(front="id: 12\ntitle: A story"), "id must be a string"),
        (document(body="Only text.\n"), "no '## Acceptance criteria' section"),
        (document(body="## Acceptance criteria\n\n"), "no acceptance criteria"),
        (
            document(body="## Acceptance criteria\n\n- AC-1: a\n- AC-1: b\n"),
            "duplicate AC id AC-1",
        ),
        (document(body="## Acceptance criteria\n\n- AC-1 no colon\n"), "malformed line"),
        (document(body="## Acceptance criteria\n\n- Just a bullet\n"), "malformed line"),
        (document(body="## Acceptance criteria\n\n- AC-x: bad id\n"), "malformed line"),
    ],
)
def test_malformed_story_names_the_file_and_the_problem(source: str, problem: str) -> None:
    with pytest.raises(StoryFormatError) as error:
        parse_story(source, "stories/fraud.md")

    assert str(error.value).startswith("stories/fraud.md: ")
    assert problem in str(error.value)
