import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from atda.adapters.cli import main
from atda.adapters.http import HttpStatusError
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


PRIORITIZER = json.dumps(
    {
        "scores": [
            {"requirement_id": "S-1.R1", "likelihood": 3, "impact": 3},
            {"requirement_id": "S-1.R2", "likelihood": 1, "impact": 1},
        ]
    }
)


CRITIC = json.dumps({"findings": []})
SINGLE = json.dumps(
    {
        **json.loads(ANALYST),
        **json.loads(DESIGNER),
        **json.loads(PRIORITIZER),
    }
)


def script(tmp_path: Path, name: str, answers: list[str]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(answers))
    return path


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
    path.write_text(json.dumps([ANALYST, DESIGNER, PRIORITIZER]))
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
    assert [r["risk"] for r in printed["requirements"]] == [
        {"likelihood": 3, "impact": 3},
        {"likelihood": 1, "impact": 1},
    ]
    assert {c["priority"] for c in printed["test_cases"]} == {"P1"}


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


def test_a_script_without_the_prioritizers_answer_exits_with_2(
    tmp_path: Path, story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    short = tmp_path / "two.json"
    short.write_text(json.dumps([ANALYST, DESIGNER]))

    code = main(design(story, context, short))

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
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


@pytest.mark.parametrize(
    ("variant", "answers"),
    [
        ("single-prompt", [SINGLE]),
        ("pipeline", [ANALYST, DESIGNER, PRIORITIZER]),
        ("pipeline-with-critic", [ANALYST, DESIGNER, CRITIC, PRIORITIZER]),
    ],
)
def test_each_variant_runs_with_its_own_number_of_scripted_answers(
    tmp_path: Path,
    story: Path,
    context: Path,
    capsys: pytest.CaptureFixture[str],
    variant: str,
    answers: list[str],
) -> None:
    responses = script(tmp_path, variant, answers)

    code = main([*design(story, context, responses), "--variant", variant])

    printed = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [r["id"] for r in printed["requirements"]] == ["S-1.R1", "S-1.R2"]
    assert [c["overrides"]["amount"] for c in printed["test_cases"]] == [
        "9999.99",
        "10000",
        "10000.01",
    ]
    assert {c["priority"] for c in printed["test_cases"]} == {"P1"}


def test_the_default_variant_is_the_pipeline(
    story: Path, context: Path, responses: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(design(story, context, responses)) == 0

    assert json.loads(capsys.readouterr().out)["requirements"]


def test_a_variant_with_too_few_scripted_answers_exits_with_2(
    tmp_path: Path, story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    short = script(tmp_path, "short", [ANALYST, DESIGNER, PRIORITIZER])

    code = main([*design(story, context, short), "--variant", "pipeline-with-critic"])

    captured = capsys.readouterr()
    assert code == 2
    assert "no scripted response left" in captured.err


def test_an_unknown_variant_is_a_usage_error(story: Path, context: Path, responses: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([*design(story, context, responses), "--variant", "everything"])

    assert exit_info.value.code == 2


PROFILE = "claude-sonnet-5-5"
KEY = "sk-test-0123456789"


def messages_api(answers: list[str]) -> list[dict[str, object]]:
    return [
        {
            "content": [{"type": "text", "text": answer}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
        for answer in answers
    ]


def with_profile(story: Path, context: Path, *extra: str) -> list[str]:
    return ["design", str(story), "--context", str(context), *extra]


def stub_transport(
    monkeypatch: pytest.MonkeyPatch, scripted: Sequence[object]
) -> list[tuple[str, dict[str, object], dict[str, str]]]:
    outcomes = list(scripted)
    calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def transport(
        url: str, payload: dict[str, object], headers: dict[str, str], *, timeout: float
    ) -> dict[str, object]:
        calls.append((url, payload, headers))
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, dict)
        return outcome

    monkeypatch.setattr("atda.adapters.profiles.post_json", transport)
    return calls


def test_a_profile_builds_the_client_and_runs_the_pipeline(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    calls = stub_transport(monkeypatch, [*messages_api([ANALYST, DESIGNER, PRIORITIZER])])

    code = main(with_profile(story, context, "--profile", PROFILE))

    captured = capsys.readouterr()
    assert code == 0
    assert [r["id"] for r in json.loads(captured.out)["requirements"]] == ["S-1.R1", "S-1.R2"]
    assert len(calls) == 3
    assert {c[0] for c in calls} == {"https://api.anthropic.com/v1/messages"}
    assert {c[1]["model"] for c in calls} == {"claude-sonnet-5-5"}
    assert KEY not in captured.out + captured.err


def test_a_profile_works_with_another_variant(
    story: Path, context: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    calls = stub_transport(monkeypatch, [*messages_api([SINGLE])])

    code = main(with_profile(story, context, "--profile", PROFILE, "--variant", "single-prompt"))

    assert code == 0
    assert len(calls) == 1


def test_an_unknown_profile_exits_with_2_and_lists_the_available_names(
    story: Path, context: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(with_profile(story, context, "--profile", "no-such-profile"))

    err = capsys.readouterr().err
    assert code == 2
    assert "no-such-profile" in err
    assert PROFILE in err


def test_a_missing_key_exits_with_2_and_names_the_variable(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    code = main(with_profile(story, context, "--profile", PROFILE))

    err = capsys.readouterr().err
    assert code == 2
    assert "ANTHROPIC_API_KEY" in err


def test_an_http_failure_exits_with_1_and_does_not_print_the_key(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    stub_transport(monkeypatch, [HttpStatusError(401, '{"error": "invalid x-api-key"}')])

    code = main(with_profile(story, context, "--profile", PROFILE))

    captured = capsys.readouterr()
    assert code == 1
    assert "401" in captured.err
    assert KEY not in captured.out + captured.err


def test_a_cut_off_answer_exits_with_1(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    cut = messages_api(['{"requirements"'])
    cut[0]["stop_reason"] = "max_tokens"
    stub_transport(monkeypatch, cut)

    code = main(with_profile(story, context, "--profile", PROFILE))

    assert code == 1
    assert "max_tokens" in capsys.readouterr().err


def test_a_profile_and_fake_responses_together_are_a_usage_error(
    story: Path, context: Path, responses: Path
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(with_profile(story, context, "--profile", PROFILE, "--fake-responses", str(responses)))

    assert exit_info.value.code == 2


def test_neither_a_profile_nor_fake_responses_is_a_usage_error(story: Path, context: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(with_profile(story, context))

    assert exit_info.value.code == 2


COMPAT_PROFILE = "groq-gpt-oss-120b"
COMPAT_KEY = "gsk-test-0123456789"


def chat_completions(answers: list[str]) -> list[dict[str, object]]:
    return [
        {
            "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
        for answer in answers
    ]


def test_an_openai_compatible_profile_runs_the_pipeline(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", COMPAT_KEY)
    calls = stub_transport(monkeypatch, chat_completions([ANALYST, DESIGNER, PRIORITIZER]))

    code = main(with_profile(story, context, "--profile", COMPAT_PROFILE))

    captured = capsys.readouterr()
    assert code == 0
    assert [r["id"] for r in json.loads(captured.out)["requirements"]] == ["S-1.R1", "S-1.R2"]
    assert len(calls) == 3
    assert {c[0] for c in calls} == {"https://api.groq.com/openai/v1/chat/completions"}
    assert {c[1]["model"] for c in calls} == {"openai/gpt-oss-120b"}
    assert COMPAT_KEY not in captured.out + captured.err


def test_a_missing_key_of_an_openai_compatible_profile_exits_with_2(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    code = main(with_profile(story, context, "--profile", COMPAT_PROFILE))

    assert code == 2
    assert "GROQ_API_KEY" in capsys.readouterr().err


def test_a_response_without_usage_exits_with_1_and_does_not_print_the_key(
    story: Path,
    context: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", COMPAT_KEY)
    body = chat_completions([ANALYST])[0]
    del body["usage"]
    stub_transport(monkeypatch, [body])

    code = main(with_profile(story, context, "--profile", COMPAT_PROFILE))

    captured = capsys.readouterr()
    assert code == 1
    assert "usage" in captured.err
    assert COMPAT_KEY not in captured.out + captured.err
