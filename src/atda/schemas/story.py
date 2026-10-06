import re

import yaml
from pydantic import BaseModel, ConfigDict

from atda.schemas.strict_yaml import load_yaml

CRITERIA_HEADING = "## Acceptance criteria"
CRITERION_LINE = re.compile(r"^- (AC-\d+): (.+)$")


class StoryFormatError(ValueError):
    pass


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str


class Story(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    text: str
    acceptance_criteria: tuple[AcceptanceCriterion, ...]


def parse_story(source: str, name: str) -> Story:
    lines = source.replace("\r\n", "\n").split("\n")
    front, body = _split_front_matter(lines, name)
    story_id = _front_matter_string(front, "id", name)
    title = _front_matter_string(front, "title", name)

    heading = next((i for i, line in enumerate(body) if line.strip() == CRITERIA_HEADING), None)
    if heading is None:
        raise StoryFormatError(f"{name}: no '{CRITERIA_HEADING}' section")
    end = next(
        (i for i in range(heading + 1, len(body)) if body[i].startswith(("# ", "## "))), len(body)
    )

    criteria = _parse_criteria(body[heading + 1 : end], name)
    parts = ("\n".join(body[:heading]).strip(), "\n".join(body[end:]).strip())
    return Story(
        id=story_id,
        title=title,
        text="\n\n".join(part for part in parts if part),
        acceptance_criteria=criteria,
    )


def _split_front_matter(lines: list[str], name: str) -> tuple[object, list[str]]:
    if lines[0].strip() != "---":
        raise StoryFormatError(f"{name}: no front matter, the file must start with '---'")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise StoryFormatError(f"{name}: front matter is not closed with '---'") from None
    try:
        front = load_yaml("\n".join(lines[1:end]))
    except yaml.YAMLError as error:
        raise StoryFormatError(f"{name}: front matter is not valid YAML: {error}") from error
    return front, lines[end + 1 :]


def _front_matter_string(front: object, key: str, name: str) -> str:
    if not isinstance(front, dict) or key not in front:
        raise StoryFormatError(f"{name}: front matter is missing {key}")
    value = front[key]
    if not isinstance(value, str) or not value.strip():
        raise StoryFormatError(f"{name}: front matter {key} must be a string")
    return value.strip()


def _parse_criteria(lines: list[str], name: str) -> tuple[AcceptanceCriterion, ...]:
    criteria: list[AcceptanceCriterion] = []
    seen: set[str] = set()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        match = CRITERION_LINE.match(line)
        if match is None:
            raise StoryFormatError(f"{name}: malformed line in acceptance criteria: {line!r}")
        criterion_id, text = match.groups()
        if criterion_id in seen:
            raise StoryFormatError(f"{name}: duplicate AC id {criterion_id}")
        seen.add(criterion_id)
        criteria.append(AcceptanceCriterion(id=criterion_id, text=text.strip()))
    if not criteria:
        raise StoryFormatError(f"{name}: no acceptance criteria under '{CRITERIA_HEADING}'")
    return tuple(criteria)
