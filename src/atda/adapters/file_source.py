from pathlib import Path

from atda.ports.requirements import RequirementsSource
from atda.schemas.story import Story, StoryFormatError, parse_story
from atda.schemas.test_context import TestContext, TestContextError, parse_test_context


# Subclassing the Protocol makes mypy check the signature here, since nothing consumes
# the port yet.
class FileSource(RequirementsSource):
    def load(self, ref: str) -> Story:
        return parse_story(_read_text(Path(ref), StoryFormatError), ref)


def load_test_context(path: Path) -> TestContext:
    return parse_test_context(_read_text(path, TestContextError), str(path))


def _read_text(path: Path, error: type[ValueError]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise error(f"{path}: not valid UTF-8 text") from None
