import json
import subprocess
import sys
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
statuses: [done]
outcome_keys: [ok]
"""

ANSWER = json.dumps(
    {
        "requirements": [
            {"ac_id": "AC-1", "text": "Something holds."},
            {"ac_id": "AC-2", "text": "Something else holds."},
        ],
        "gaps": [{"ac_id": None, "text": "The story does not say when."}],
    }
)


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


@pytest.fixture
def responses(tmp_path: Path) -> Path:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps([ANSWER]))
    return path


def design(story: Path, context: Path, responses: Path) -> list[str]:
    return ["design", str(story), "--context", str(context), "--fake-responses", str(responses)]


def test_design_prints_the_inputs_requirements_and_gaps_as_json(
    story: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(design(story, context, responses))

    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert code == 0
    assert captured.err == ""
    assert printed["story"]["id"] == "S-1"
    assert [c["id"] for c in printed["story"]["acceptance_criteria"]] == ["AC-1", "AC-2"]
    assert printed["test_context"]["target"] == "some.target"
    assert [(r["id"], r["ac_id"]) for r in printed["requirements"]] == [
        ("S-1.R1", "AC-1"),
        ("S-1.R2", "AC-2"),
    ]
    assert printed["gaps"] == [{"ac_id": None, "text": "The story does not say when."}]


def test_a_missing_story_file_exits_with_2_and_names_the_path(
    tmp_path: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(design(tmp_path / "absent.md", context, responses))

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "absent.md" in captured.err
    assert captured.err.count("\n") == 1


def test_a_malformed_story_exits_with_2_and_gives_the_problem(
    tmp_path: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.md"
    broken.write_text("---\nid: S-1\ntitle: A story\n---\nOnly text.\n")

    code = main(design(broken, context, responses))

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "broken.md" in captured.err
    assert "no '## Acceptance criteria' section" in captured.err


def test_a_malformed_test_context_exits_with_2_and_gives_the_problem(
    tmp_path: Path, story: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("target: only\n")

    code = main(design(story, broken, responses))

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "broken.yaml" in captured.err
    assert "outcome_keys" in captured.err


def test_a_file_that_is_not_utf8_exits_with_2_without_a_traceback(
    tmp_path: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"\xff\xfe\x00 not text")

    code = main(design(binary, context, responses))

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error: ")
    assert "binary.md" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        ("not json", "not valid JSON"),
        ('{"a": 1}', "must be a JSON list of strings"),
        ("[1, 2]", "must be a JSON list of strings"),
    ],
)
def test_a_bad_responses_file_exits_with_2(
    tmp_path: Path,
    story: Path,
    context: Path,
    capsys: pytest.CaptureFixture[str],
    content: str,
    problem: str,
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(content)

    code = main(design(story, context, bad))

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "bad.json" in captured.err
    assert problem in captured.err


def test_too_few_scripted_answers_exit_with_2(
    tmp_path: Path, story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("[]")

    code = main(design(story, context, empty))

    captured = capsys.readouterr()
    assert code == 2
    assert "no scripted response left" in captured.err


def test_an_analysis_the_model_cannot_get_right_exits_with_1(
    tmp_path: Path, story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad-answers.json"
    bad.write_text(json.dumps(["nope", "nope", "nope"]))

    code = main(design(story, context, bad))

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: no valid answer after 3 attempts")


@pytest.mark.parametrize("missing", ["--context", "--fake-responses"])
def test_a_missing_required_option_is_a_usage_error(
    story: Path, context: Path, responses: Path, missing: str
) -> None:
    argv = design(story, context, responses)
    index = argv.index(missing)
    del argv[index : index + 2]

    with pytest.raises(SystemExit) as exit_info:
        main(argv)

    assert exit_info.value.code == 2


def test_the_atda_script_runs_the_design_command(
    story: Path, context: Path, responses: Path
) -> None:
    script = Path(sys.executable).parent / "atda"

    result = subprocess.run(
        [str(script), *design(story, context, responses)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["requirements"][0]["id"] == "S-1.R1"
