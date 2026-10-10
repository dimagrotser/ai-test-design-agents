from pathlib import Path

import pytest

from atda.adapters.corpus import load_agent_view, load_manifest
from atda.schemas.corpus import ManifestError
from atda.schemas.story import StoryFormatError

SHA = "84b889bb0e39b235a5c8448266ec5d3888552997"

STORY = """\
---
id: FRAUD-1
title: Reject risky transactions
---
Text.

## Acceptance criteria

- AC-1: An amount over 10 000 is rejected.
"""

CONTEXT = """\
target: fraud.evaluate
nominal_input:
  amount: "100"
statuses: [approved, rejected]
outcome_keys: [amount_limit]
"""

MANIFEST = f"""\
sut_commit: {SHA}
stories:
  FRAUD-1:
    story: stories/fraud.md
    test_context: stories/fraud.context.yaml
    sut_config: {{max_amount: "10000"}}
    split: held-out
    class: normal
"""


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    base = tmp_path / "eval"
    (base / "stories").mkdir(parents=True)
    (base / "stories" / "fraud.md").write_text(STORY)
    (base / "stories" / "fraud.context.yaml").write_text(CONTEXT)
    (base / "manifest.yaml").write_text(MANIFEST)
    return base / "manifest.yaml"


def test_paths_are_resolved_against_the_directory_of_the_manifest(corpus: Path) -> None:
    manifest = load_manifest(corpus)

    entry = manifest.stories["FRAUD-1"]
    assert entry.story == str(corpus.parent / "stories" / "fraud.md")
    assert entry.test_context == str(corpus.parent / "stories" / "fraud.context.yaml")
    assert entry.sut_config == {"max_amount": "10000"}


def test_a_missing_test_context_file_is_rejected_with_the_story_and_the_path(
    corpus: Path,
) -> None:
    (corpus.parent / "stories" / "fraud.context.yaml").unlink()

    with pytest.raises(ManifestError) as error:
        load_manifest(corpus)

    message = str(error.value)
    assert message.startswith(f"{corpus}: FRAUD-1: test context file not found: ")
    assert "fraud.context.yaml" in message


def test_a_missing_story_file_is_rejected_with_the_story_and_the_path(corpus: Path) -> None:
    (corpus.parent / "stories" / "fraud.md").unlink()

    with pytest.raises(ManifestError, match=r"FRAUD-1: story file not found: .*fraud\.md"):
        load_manifest(corpus)


def test_a_manifest_that_is_not_valid_yaml_is_rejected_with_its_name(corpus: Path) -> None:
    corpus.write_text("stories: [unclosed\n")

    with pytest.raises(ManifestError, match="manifest.yaml: not valid YAML"):
        load_manifest(corpus)


def test_a_manifest_that_is_not_utf8_is_rejected_with_its_name(corpus: Path) -> None:
    corpus.write_bytes(b"\xff\xfe\x00 not text")

    with pytest.raises(ManifestError, match="manifest.yaml: not valid UTF-8"):
        load_manifest(corpus)


def test_a_missing_manifest_file_is_reported_with_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="absent.yaml"):
        load_manifest(tmp_path / "absent.yaml")


def test_the_agent_view_has_the_story_and_the_test_context_only(corpus: Path) -> None:
    manifest = load_manifest(corpus)

    view = load_agent_view(manifest, "FRAUD-1")

    assert view.story.id == "FRAUD-1"
    assert view.test_context.target == "fraud.evaluate"
    dumped = view.model_dump()
    assert set(dumped) == {"story", "test_context"}
    assert "sut_config" not in str(dumped)
    assert "held-out" not in str(dumped)


def test_a_story_file_with_a_different_id_than_its_manifest_key_is_rejected(corpus: Path) -> None:
    (corpus.parent / "stories" / "fraud.md").write_text(STORY.replace("FRAUD-1", "OTHER-1"))
    manifest = load_manifest(corpus)

    with pytest.raises(ManifestError, match="FRAUD-1: .*fraud.md declares id OTHER-1"):
        load_agent_view(manifest, "FRAUD-1")


def test_an_unknown_story_id_is_rejected(corpus: Path) -> None:
    with pytest.raises(ManifestError, match="unknown story id NOPE"):
        load_agent_view(load_manifest(corpus), "NOPE")


def test_a_malformed_story_file_is_reported_by_the_story_parser(corpus: Path) -> None:
    (corpus.parent / "stories" / "fraud.md").write_text("no front matter\n")
    manifest = load_manifest(corpus)

    with pytest.raises(StoryFormatError, match="fraud.md"):
        load_agent_view(manifest, "FRAUD-1")
