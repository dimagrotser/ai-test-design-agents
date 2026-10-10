import argparse
import json
import sys
from pathlib import Path

from atda.adapters.errors import IncompleteResponse, MalformedResponse, MissingApiKey
from atda.adapters.fake import FakeLLMClient, ScriptExhausted
from atda.adapters.file_source import FileSource, load_test_context
from atda.adapters.http import HttpError
from atda.adapters.profiles import UnknownProfile, build_client, load_profile
from atda.ports.llm import LLMClient
from atda.report import render_json, render_markdown
from atda.schemas.provider_profile import ProviderProfileError
from atda.schemas.story import Story, StoryFormatError
from atda.schemas.test_context import TestContextError
from atda.schemas.test_design import TestDesign
from atda.structured_generation import StructuredGenerationError
from atda.variants import Variant, run_variant

# The CLI drives the core, so it is an adapter. Living here is what lets it import
# FileSource while the core still never imports from adapters/.


class ResponsesFileError(ValueError):
    pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        story = FileSource().load(args.story)
        context = load_test_context(Path(args.context))
        client = _client(args)
        design = run_variant(Variant(args.variant), client, story, context).value
        written = _write_report(Path(args.out), story, design) if args.out else []
    except (
        StoryFormatError,
        TestContextError,
        ResponsesFileError,
        ScriptExhausted,
        UnknownProfile,
        ProviderProfileError,
        MissingApiKey,
        OSError,
    ) as e:
        return _fail(e, 2)
    except (StructuredGenerationError, HttpError, IncompleteResponse, MalformedResponse) as error:
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


def _client(args: argparse.Namespace) -> LLMClient:
    if args.profile:
        return build_client(load_profile(args.profile))
    return FakeLLMClient(_load_responses(Path(args.fake_responses)))


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
    source = design.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--profile",
        help="name of a Provider Profile: run against that model (needs its key variable)",
    )
    source.add_argument(
        "--fake-responses",
        help=(
            "JSON list of model answers, in call order: one for single-prompt, "
            "analyst, designer, prioritizer for pipeline, plus a critic after each "
            "designer for pipeline-with-critic"
        ),
    )
    design.add_argument(
        "--variant",
        choices=[v.value for v in Variant],
        default=Variant.PIPELINE.value,
        help="how the Test Design is produced (default: pipeline)",
    )
    design.add_argument("--out", help="directory for test-design.json and test-design.md")
    return parser
