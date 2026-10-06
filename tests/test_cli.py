import json
from pathlib import Path

import pytest

from atda.adapters.cli import main

STORY = """\
---
id: S-1
title: A story
---
Some text.

## Acceptance criteria

- AC-1: Something holds.
- AC-2: Something else holds.
"""

CONTEXT = """\
target: some.target
nominal_input:
  amount: 1
outcome_keys: [ok]
"""


@pytest.fixture
def story(tmp_path: Path) -> Path:
    path = tmp_path / "story.md"
    path.write_text(STORY)
    return path


@pytest.fixture
def context(tmp_path: Path) -> Path:
    path = tmp_path / "story.context.yaml"
    path.write_text(CONTEXT)
    return path


def test_design_prints_the_validated_inputs_as_json(
    story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["design", str(story), "--context", str(context)])

    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert code == 0
    assert captured.err == ""
    assert printed["story"]["id"] == "S-1"
    assert [c["id"] for c in printed["story"]["acceptance_criteria"]] == ["AC-1", "AC-2"]
    assert printed["test_context"]["target"] == "some.target"


def test_a_missing_story_file_exits_with_2_and_names_the_path(
    tmp_path: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["design", str(tmp_path / "absent.md"), "--context", str(context)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "absent.md" in captured.err
    assert captured.err.count("\n") == 1


def test_a_malformed_story_exits_with_2_and_gives_the_problem(
    tmp_path: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.md"
    broken.write_text("---\nid: S-1\ntitle: A story\n---\nOnly text.\n")

    code = main(["design", str(broken), "--context", str(context)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "broken.md" in captured.err
    assert "no '## Acceptance criteria' section" in captured.err


def test_a_malformed_test_context_exits_with_2_and_gives_the_problem(
    tmp_path: Path, story: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("target: only\n")

    code = main(["design", str(story), "--context", str(broken)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "broken.yaml" in captured.err
    assert "outcome_keys" in captured.err


def test_a_file_that_is_not_utf8_exits_with_2_without_a_traceback(
    tmp_path: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"\xff\xfe\x00 not text")

    code = main(["design", str(binary), "--context", str(context)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error: ")
    assert "binary.md" in captured.err
    assert "Traceback" not in captured.err


def test_a_missing_context_option_is_a_usage_error(story: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["design", str(story)])

    assert exit_info.value.code == 2
