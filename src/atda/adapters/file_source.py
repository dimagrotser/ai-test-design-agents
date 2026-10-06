from pathlib import Path

from atda.ports.requirements import RequirementsSource
from atda.schemas.story import Story, parse_story
from atda.schemas.test_context import TestContext, parse_test_context


# Subclassing the Protocol makes mypy check the signature here, since nothing consumes
# the port yet.
class FileSource(RequirementsSource):
    def load(self, ref: str) -> Story:
        return parse_story(Path(ref).read_text(encoding="utf-8"), ref)


def load_test_context(path: Path) -> TestContext:
    return parse_test_context(path.read_text(encoding="utf-8"), str(path))
