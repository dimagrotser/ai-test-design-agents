import argparse
import json
import sys
from pathlib import Path

from atda.adapters.file_source import FileSource, load_test_context
from atda.schemas.story import StoryFormatError
from atda.schemas.test_context import TestContextError

# The CLI drives the core, so it is an adapter. Living here is what lets it import
# FileSource while the core still never imports from adapters/.


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        story = FileSource().load(args.story)
        context = load_test_context(Path(args.context))
    except (StoryFormatError, TestContextError, OSError) as error:
        print("error: " + " ".join(str(error).split()), file=sys.stderr)
        return 2
    design = {
        "story": story.model_dump(mode="json"),
        "test_context": context.model_dump(mode="json"),
    }
    print(json.dumps(design, indent=2, ensure_ascii=False))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atda")
    commands = parser.add_subparsers(dest="command", required=True)
    design = commands.add_parser("design", help="turn a Story into a Test Design")
    design.add_argument("story", help="path to the Story file")
    design.add_argument("--context", required=True, help="path to the Test Context file")
    return parser
