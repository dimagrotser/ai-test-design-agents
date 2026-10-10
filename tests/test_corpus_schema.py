import pytest
from pydantic import ValidationError

from atda.schemas.corpus import (
    AgentView,
    HeldOutStoryError,
    ManifestError,
    parse_manifest,
)
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_context import TestContext

SHA = "84b889bb0e39b235a5c8448266ec5d3888552997"

VALID = f"""\
sut_commit: {SHA}
stories:
  FRAUD-1:
    story: stories/fraud.md
    test_context: stories/fraud.context.yaml
    sut_config:
      max_amount: "10000"
      blocked_countries: [KP, IR, SY]
      velocity_limit: 5
    split: held-out
    class: normal
  RULES-1:
    story: stories/rules.md
    test_context: stories/rules.context.yaml
    split: dev
    class: gap-probe
"""


def test_a_valid_manifest_keeps_the_pinned_commit_and_every_story_entry() -> None:
    manifest = parse_manifest(VALID, "manifest.yaml")

    assert manifest.sut_commit == SHA
    assert list(manifest.stories) == ["FRAUD-1", "RULES-1"]
    fraud = manifest.stories["FRAUD-1"]
    assert (fraud.story, fraud.test_context) == ("stories/fraud.md", "stories/fraud.context.yaml")
    assert (fraud.split, fraud.story_class) == ("held-out", "normal")
    assert fraud.sut_config == {
        "max_amount": "10000",
        "blocked_countries": ["KP", "IR", "SY"],
        "velocity_limit": 5,
    }
    rules = manifest.stories["RULES-1"]
    assert (rules.split, rules.story_class, rules.sut_config) == ("dev", "gap-probe", {})


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        (VALID.replace("split: held-out", "split: test"), "stories.FRAUD-1.split"),
        (VALID.replace("class: normal", "class: weird"), "stories.FRAUD-1.class"),
        (VALID.replace("    split: held-out\n", ""), "stories.FRAUD-1.split"),
        (VALID.replace("    class: normal\n", ""), "stories.FRAUD-1.class"),
        (VALID.replace("    split: dev\n", "    split: dev\n    owner: me\n"), "owner"),
        (f"sut_commit: {SHA}\nstories: {{}}\n", "stories"),
        (f"sut_commit: {SHA}\n", "stories"),
        ("stories: {}\n", "sut_commit"),
        ("stories: [unclosed\n", "not valid YAML"),
        ("- a\n- list\n", "must be a mapping"),
    ],
)
def test_a_malformed_manifest_names_the_file_and_the_problem(source: str, problem: str) -> None:
    with pytest.raises(ManifestError) as error:
        parse_manifest(source, "eval/manifest.yaml")

    assert str(error.value).startswith("eval/manifest.yaml: ")
    assert problem in str(error.value)


@pytest.mark.parametrize(
    "reference",
    [
        "main",
        "v1.2",
        "84b889b",
        SHA[:39],
        SHA + "0",
        SHA.upper(),
        "1234567890123456789012345678901234567890",
    ],
)
def test_a_sut_reference_that_is_not_a_full_lowercase_commit_sha_is_rejected(
    reference: str,
) -> None:
    source = VALID.replace(f"sut_commit: {SHA}", f"sut_commit: {reference}")

    with pytest.raises(ManifestError, match="sut_commit"):
        parse_manifest(source, "manifest.yaml")


def test_the_error_for_a_branch_name_says_what_is_expected() -> None:
    source = VALID.replace(f"sut_commit: {SHA}", "sut_commit: main")

    with pytest.raises(ManifestError, match="full 40-character commit SHA, got 'main'"):
        parse_manifest(source, "manifest.yaml")


def test_the_agent_view_holds_a_story_and_a_test_context_and_nothing_else() -> None:
    assert set(AgentView.model_fields) == {"story", "test_context"}
    story = Story(
        id="S-1",
        title="T",
        text="",
        acceptance_criteria=(AcceptanceCriterion(id="AC-1", text="x"),),
    )
    context = TestContext(target="t", nominal_input={"a": 1}, statuses=("ok",), outcome_keys=("k",))

    view = AgentView(story=story, test_context=context)

    assert view.story == story
    with pytest.raises(ValidationError):
        AgentView.model_validate({"story": story, "test_context": context, "split": "held-out"})


def test_a_dev_story_may_be_recorded() -> None:
    manifest = parse_manifest(VALID, "manifest.yaml")

    assert manifest.require_dev("RULES-1").split == "dev"


def test_a_held_out_story_may_not_be_recorded() -> None:
    manifest = parse_manifest(VALID, "manifest.yaml")

    with pytest.raises(HeldOutStoryError, match="FRAUD-1"):
        manifest.require_dev("FRAUD-1")


def test_an_unknown_story_id_is_rejected() -> None:
    manifest = parse_manifest(VALID, "manifest.yaml")

    with pytest.raises(ManifestError, match="unknown story id NOPE"):
        manifest.require_dev("NOPE")
