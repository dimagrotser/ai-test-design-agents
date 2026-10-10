import json
from pathlib import Path

import pytest

# Story, Test Context, scripted answers and the transport stub of the CLI tests.
from test_cli import (
    ANALYST,
    CONTEXT,
    DESIGNER,
    KEY,
    PRIORITIZER,
    PROFILE,
    SINGLE,
    STORY,
    messages_api,
    stub_transport,
)

from atda.adapters.cli import main
from atda.adapters.http import HttpStatusError
from atda.schemas.test_design import TestDesign

SHA = "a" * 40
MANIFEST = f"""\
sut_commit: {SHA}
stories:
  S-1:
    story: stories/story.md
    test_context: stories/story.context.yaml
    split: dev
    class: normal
  H-1:
    story: stories/story.md
    test_context: stories/story.context.yaml
    split: held-out
    class: normal
"""


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    base = tmp_path / "corpus"
    (base / "stories").mkdir(parents=True)
    (base / "stories" / "story.md").write_text(STORY)
    (base / "stories" / "story.context.yaml").write_text(CONTEXT)
    path = base / "manifest.yaml"
    path.write_text(MANIFEST)
    return path


@pytest.fixture(autouse=True)
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)


def record(manifest: Path, out: Path, story_id: str, *extra: str) -> list[str]:
    return [
        "record",
        story_id,
        "--manifest",
        str(manifest),
        "--profile",
        PROFILE,
        "--out",
        str(out),
        *extra,
    ]


def test_a_dev_story_is_recorded_into_fixtures_and_a_test_design(
    manifest: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    calls = stub_transport(monkeypatch, messages_api([ANALYST, DESIGNER, PRIORITIZER]))

    code = main(record(manifest, out, "S-1"))

    captured = capsys.readouterr()
    assert code == 0
    assert len(calls) == 3
    assert len(list((out / "fixtures").glob("*.json"))) == 3
    design = TestDesign.model_validate_json((out / "test-design.json").read_text(encoding="utf-8"))
    assert [r.id for r in design.requirements] == ["S-1.R1", "S-1.R2"]
    assert "3" in captured.out
    assert KEY not in captured.out + captured.err


def test_the_recording_runs_at_temperature_zero(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_transport(monkeypatch, messages_api([ANALYST, DESIGNER, PRIORITIZER]))

    main(record(manifest, tmp_path / "out", "S-1"))

    assert {c[1]["temperature"] for c in calls} == {0.0}


def test_a_variant_can_be_recorded(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    stub_transport(monkeypatch, messages_api([SINGLE]))

    code = main(record(manifest, out, "S-1", "--variant", "single-prompt"))

    assert code == 0
    assert len(list((out / "fixtures").glob("*.json"))) == 1


def test_no_key_and_no_header_name_reach_the_files(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    stub_transport(monkeypatch, messages_api([ANALYST, DESIGNER, PRIORITIZER]))

    main(record(manifest, out, "S-1"))

    for path in out.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert KEY not in text
        assert "x-api-key" not in text.lower()


def test_a_held_out_story_exits_non_zero_and_writes_nothing(
    manifest: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    calls = stub_transport(monkeypatch, [])

    code = main(record(manifest, out, "H-1"))

    assert code == 2
    assert "held-out" in capsys.readouterr().err
    assert not out.exists()
    assert calls == []


def test_the_held_out_check_runs_before_the_profile_and_the_key_are_touched(
    manifest: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    argv = record(manifest, tmp_path / "out", "H-1")
    argv[argv.index(PROFILE)] = "no-such-profile"

    code = main(argv)

    err = capsys.readouterr().err
    assert code == 2
    assert "held-out" in err
    assert "no-such-profile" not in err


def test_an_unknown_story_id_exits_non_zero_and_writes_nothing(
    manifest: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"

    code = main(record(manifest, out, "X-9"))

    assert code == 2
    assert "X-9" in capsys.readouterr().err
    assert not out.exists()


def test_a_missing_manifest_exits_with_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(record(tmp_path / "none.yaml", tmp_path / "out", "S-1"))

    assert code == 2
    assert "none.yaml" in capsys.readouterr().err


def test_a_missing_key_exits_with_2_before_anything_is_written(
    manifest: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    out = tmp_path / "out"

    code = main(record(manifest, out, "S-1"))

    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not out.exists()


def test_a_failing_first_call_exits_with_1_and_writes_nothing(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    stub_transport(monkeypatch, [HttpStatusError(500, "overloaded")])

    code = main(record(manifest, out, "S-1"))

    assert code == 1
    assert not out.exists()


def test_the_recorded_design_is_the_canonical_json_of_the_run(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    stub_transport(monkeypatch, messages_api([ANALYST, DESIGNER, PRIORITIZER]))

    main(record(manifest, out, "S-1"))

    text = (out / "test-design.json").read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text)["story_id"] == "S-1"


def recorded(manifest: Path, out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_transport(monkeypatch, messages_api([ANALYST, DESIGNER, PRIORITIZER]))
    assert main(record(manifest, out, "S-1")) == 0


def replay(manifest: Path, directory: Path, *extra: str) -> list[str]:
    base = manifest.parent / "stories"
    return [
        "design",
        str(base / "story.md"),
        "--context",
        str(base / "story.context.yaml"),
        "--profile",
        PROFILE,
        "--replay",
        str(directory),
        *extra,
    ]


def test_design_with_replay_reproduces_the_recording_without_a_key_or_a_network(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    recorded(manifest, out, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    calls = stub_transport(monkeypatch, [])
    replayed = tmp_path / "replayed"

    code = main(replay(manifest, out / "fixtures", "--out", str(replayed)))

    assert code == 0
    assert calls == []
    assert (replayed / "test-design.json").read_bytes() == (out / "test-design.json").read_bytes()


def test_a_changed_story_fails_the_replay_with_a_missing_fixture_error(
    manifest: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    recorded(manifest, out, monkeypatch)
    story = manifest.parent / "stories" / "story.md"
    story.write_text(story.read_text().replace("10 000", "10 001"))

    code = main(replay(manifest, out / "fixtures"))

    err = capsys.readouterr().err
    assert code == 1
    assert "no recorded response for key" in err


def test_a_missing_replay_directory_exits_with_2(
    manifest: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(replay(manifest, tmp_path / "nowhere"))

    assert code == 2
    assert "nowhere" in capsys.readouterr().err


def test_replay_without_a_profile_is_a_usage_error(manifest: Path, tmp_path: Path) -> None:
    base = manifest.parent / "stories"
    answers = tmp_path / "answers.json"
    answers.write_text("[]")

    with pytest.raises(SystemExit) as exit_info:
        main(
            [
                "design",
                str(base / "story.md"),
                "--context",
                str(base / "story.context.yaml"),
                "--fake-responses",
                str(answers),
                "--replay",
                str(tmp_path),
            ]
        )

    assert exit_info.value.code == 2
