from pathlib import Path

from atda.adapters.file_source import FileSource, load_test_context
from atda.schemas.corpus import AgentView, CorpusManifest, ManifestError, parse_manifest


def load_manifest(path: Path) -> CorpusManifest:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ManifestError(f"{path}: not valid UTF-8 text") from None
    manifest = parse_manifest(text, str(path))
    base = path.resolve().parent
    stories = {}
    for story_id, entry in manifest.stories.items():
        story_path = base / entry.story
        context_path = base / entry.test_context
        if not story_path.is_file():
            raise ManifestError(f"{path}: {story_id}: story file not found: {story_path}")
        if not context_path.is_file():
            raise ManifestError(f"{path}: {story_id}: test context file not found: {context_path}")
        stories[story_id] = entry.model_copy(
            update={"story": str(story_path), "test_context": str(context_path)}
        )
    return manifest.model_copy(update={"stories": stories})


def load_agent_view(manifest: CorpusManifest, story_id: str) -> AgentView:
    entry = manifest.stories.get(story_id)
    if entry is None:
        raise ManifestError(f"unknown story id {story_id}")
    story = FileSource().load(entry.story)
    if story.id != story_id:
        raise ManifestError(f"{story_id}: the story file {entry.story} declares id {story.id}")
    return AgentView(story=story, test_context=load_test_context(Path(entry.test_context)))
