import argparse
import json
import sys
from pathlib import Path

from atda.adapters.fake import FakeLLMClient, ScriptExhausted
from atda.adapters.file_source import FileSource, load_test_context
from atda.pipeline import run_pipeline
from atda.report import render_json, render_markdown
from atda.schemas.story import Story, StoryFormatError
from atda.schemas.test_context import TestContextError
from atda.schemas.test_design import TestDesign
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
        design = run_pipeline(client, story, context).value
        written = _write_report(Path(args.out), story, design) if args.out else []
    except (StoryFormatError, TestContextError, ResponsesFileError, ScriptExhausted, OSError) as e:
        return _fail(e, 2)
    except StructuredGenerationError as error:
        return _fail(error, 1)
    if written:
        print("\n".join(str(path) for path in written))
        return 0
    printed = {
        "story": story.model_dump(mode="json"),
        "test_context": context.model_dump(mode="json"),
        **design.model_dump(mode="json", exclude={"story_id"}),
    }
    print(json.dumps(printed, indent=2, ensure_ascii=False))
    return 0


def _fail(error: Exception, code: int) -> int:
    print("error: " + " ".join(str(error).split()), file=sys.stderr)
    return code


def _write_report(out: Path, story: Story, design: TestDesign) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = {
        out / "test-design.json": render_json(design),
        out / "test-design.md": render_markdown(story, design),
    }
    for path, text in files.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return list(files)


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
        help="JSON list of model answers: analyst, designer, prioritizer",
    )
    design.add_argument("--out", help="directory for test-design.json and test-design.md")
    return parser
