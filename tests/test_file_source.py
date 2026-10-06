from pathlib import Path

import pytest

from atda.adapters.file_source import FileSource, load_test_context
from atda.schemas.story import StoryFormatError
from atda.schemas.test_context import TestContextError

STORY = """\
---
id: S-1
title: A story
---
## Acceptance criteria

- AC-1: Something holds.
"""

CONTEXT = """\
target: some.target
nominal_input:
  amount: 1
outcome_keys: [ok]
"""


def test_file_source_loads_a_story_from_a_path(tmp_path: Path) -> None:
    path = tmp_path / "story.md"
    path.write_text(STORY)

    story = FileSource().load(str(path))

    assert story.id == "S-1"
    assert [c.id for c in story.acceptance_criteria] == ["AC-1"]


def test_a_missing_story_file_is_reported_with_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="absent.md"):
        FileSource().load(str(tmp_path / "absent.md"))


def test_a_malformed_story_file_is_reported_with_its_path(tmp_path: Path) -> None:
    path = tmp_path / "broken.md"
    path.write_text("no front matter\n")

    with pytest.raises(StoryFormatError, match="broken.md"):
        FileSource().load(str(path))


def test_a_test_context_is_loaded_from_a_path(tmp_path: Path) -> None:
    path = tmp_path / "story.context.yaml"
    path.write_text(CONTEXT)

    context = load_test_context(path)

    assert context.target == "some.target"
    assert context.outcome_keys == ("ok",)


def test_a_missing_test_context_file_is_reported_with_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="absent.yaml"):
        load_test_context(tmp_path / "absent.yaml")


def test_a_malformed_test_context_file_is_reported_with_its_path(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("target: only\n")

    with pytest.raises(TestContextError, match="broken.yaml"):
        load_test_context(path)


def test_a_story_file_that_is_not_utf8_is_reported_with_its_path(tmp_path: Path) -> None:
    path = tmp_path / "binary.md"
    path.write_bytes(b"\xff\xfe\x00 not text")

    with pytest.raises(StoryFormatError, match="binary.md: not valid UTF-8"):
        FileSource().load(str(path))


def test_a_test_context_file_that_is_not_utf8_is_reported_with_its_path(tmp_path: Path) -> None:
    path = tmp_path / "binary.yaml"
    path.write_bytes(b"\xff\xfe\x00 not text")

    with pytest.raises(TestContextError, match="binary.yaml: not valid UTF-8"):
        load_test_context(path)
