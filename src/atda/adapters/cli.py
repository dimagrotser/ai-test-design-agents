import argparse
import json
import sys
from pathlib import Path

from atda.adapters.fake import FakeLLMClient, ScriptExhausted
from atda.adapters.file_source import FileSource, load_test_context
from atda.agents.analyst import analyze
from atda.schemas.story import StoryFormatError
from atda.schemas.test_context import TestContextError
from atda.structured_generation import StructuredGenerationError

# The CLI drives the core, so it is an adapter. Living here is what lets it import
# FileSource while the core still never imports from adapters/.


class ResponsesFileError(ValueError):
    pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        story = FileSource().load(args.story)
        context = load_test_context(Path(args.context))
        client = FakeLLMClient(_load_responses(Path(args.fake_responses)))
        analysis = analyze(client, story).value
    except (StoryFormatError, TestContextError, ResponsesFileError, ScriptExhausted, OSError) as e:
        return _fail(e, 2)
    except StructuredGenerationError as error:
        return _fail(error, 1)
    design = {
        "story": story.model_dump(mode="json"),
        "test_context": context.model_dump(mode="json"),
        **analysis.model_dump(mode="json"),
    }
    print(json.dumps(design, indent=2, ensure_ascii=False))
    return 0


def _fail(error: Exception, code: int) -> int:
    print("error: " + " ".join(str(error).split()), file=sys.stderr)
    return code


def _load_responses(path: Path) -> list[str]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ResponsesFileError(f"{path}: not valid JSON: {error}") from error
    if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
        raise ResponsesFileError(f"{path}: must be a JSON list of strings")
    return loaded


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atda")
    commands = parser.add_subparsers(dest="command", required=True)
    design = commands.add_parser("design", help="turn a Story into a Test Design")
    design.add_argument("story", help="path to the Story file")
    design.add_argument("--context", required=True, help="path to the Test Context file")
    design.add_argument(
        "--fake-responses",
        required=True,
        help="JSON list of raw model answers, used until real clients exist",
    )
    return parser
