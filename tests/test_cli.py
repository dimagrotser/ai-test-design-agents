import json
import subprocess
import sys
from pathlib import Path

import pytest

from atda.adapters.cli import main
from atda.schemas.test_design import TestDesign

STORY = """\
---
id: S-1
title: A story
---
Some text.

## Acceptance criteria

- AC-1: An amount over 10 000 is rejected.
- AC-2: Something else holds.
"""

CONTEXT = """\
target: some.target
nominal_input:
  amount: "100"
statuses: [approved, rejected]
outcome_keys: [amount_limit]
"""

ANALYST = json.dumps(
    {
        "requirements": [
            {"ac_id": "AC-1", "text": "An amount over 10000 is rejected."},
            {"ac_id": "AC-2", "text": "Something else holds."},
        ],
        "gaps": [{"ac_id": None, "text": "The story does not say when."}],
    }
)
DESIGNER = json.dumps(
    {
        "conditions": [
            {
                "technique": "BVA",
                "requirement_id": "S-1.R1",
                "input_name": "amount",
                "evidence": "over 10 000",
                "operator": ">",
                "boundary": "10000",
                "value_type": "decimal",
                "outcome_if_true": {"status": "rejected", "outcome_keys": ["amount_limit"]},
                "outcome_if_false": {"status": "approved", "outcome_keys": []},
            }
        ]
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
    path.write_text(json.dumps([ANALYST, DESIGNER]))
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
    assert [c["overrides"]["amount"] for c in printed["test_cases"]] == [
        "9999.99",
        "10000",
        "10000.01",
    ]


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


def test_a_script_with_only_the_analysts_answer_exits_with_2(
    tmp_path: Path, story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    short = tmp_path / "short.json"
    short.write_text(json.dumps([ANALYST]))

    code = main(design(story, context, short))

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


def test_out_writes_the_json_and_the_markdown_report_and_prints_their_paths(
    tmp_path: Path, story: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "reports" / "fraud"

    code = main([*design(story, context, responses), "--out", str(out)])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        str(out / "test-design.json"),
        str(out / "test-design.md"),
    ]
    saved = TestDesign.model_validate_json((out / "test-design.json").read_text(encoding="utf-8"))
    assert [r.id for r in saved.requirements] == ["S-1.R1", "S-1.R2"]
    report = (out / "test-design.md").read_text(encoding="utf-8")
    assert report.startswith("# Test design S-1: A story\n")
    assert "| AC-1: An amount over 10 000 is rejected. | S-1.R1 | TC-1, TC-2, TC-3 |" in report
    assert "| AC-2: Something else holds. | S-1.R2 | uncovered |" in report


def test_two_runs_write_identical_bytes(
    tmp_path: Path, story: Path, context: Path, responses: Path
) -> None:
    for name in ("first", "second"):
        assert main([*design(story, context, responses), "--out", str(tmp_path / name)]) == 0

    for file in ("test-design.json", "test-design.md"):
        assert (tmp_path / "first" / file).read_bytes() == (tmp_path / "second" / file).read_bytes()


def test_an_out_path_that_is_a_file_exits_with_2(
    tmp_path: Path, story: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    taken = tmp_path / "taken"
    taken.write_text("not a directory")

    code = main([*design(story, context, responses), "--out", str(taken)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "taken" in captured.err
