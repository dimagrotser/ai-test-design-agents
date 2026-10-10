import json

import pytest

from atda.adapters.fake import FakeLLMClient
from atda.prompts import load_prompt
from atda.schemas.story import AcceptanceCriterion, Story
from atda.schemas.test_context import TestContext
from atda.schemas.test_design import TestDesign
from atda.variants import Variant, run_variant

STORY = Story(
    id="FRAUD-1",
    title="Reject risky transactions",
    text="",
    acceptance_criteria=(
        AcceptanceCriterion(id="AC-1", text="An amount over 10 000 is rejected."),
        AcceptanceCriterion(id="AC-2", text="Transactions from KP, IR or SY are rejected."),
    ),
)
CONTEXT = TestContext(
    target="fraud.evaluate",
    nominal_input={"amount": "100", "country": "DE"},
    statuses=("approved", "rejected"),
    outcome_keys=("amount_limit", "blocked_country"),
)

APPROVED = {"status": "approved", "outcome_keys": []}
REQUIREMENTS = [
    {"ac_id": "AC-1", "text": "An amount over 10000 is rejected."},
    {"ac_id": "AC-2", "text": "KP, IR and SY are blocked."},
]
GAPS = [{"ac_id": "AC-1", "text": "Is 10000 itself rejected?"}]
CONDITIONS = [
    {
        "technique": "BVA",
        "requirement_id": "FRAUD-1.R1",
        "input_name": "amount",
        "evidence": "over 10 000",
        "operator": ">",
        "boundary": "10000",
        "value_type": "decimal",
        "outcome_if_true": {"status": "rejected", "outcome_keys": ["amount_limit"]},
        "outcome_if_false": APPROVED,
    },
    {
        "technique": "EP",
        "requirement_id": "FRAUD-1.R2",
        "input_name": "country",
        "evidence": "from KP, IR or SY",
        "classes": [
            {
                "name": "blocked",
                "values": ["KP", "IR", "SY"],
                "outcome": {"status": "rejected", "outcome_keys": ["blocked_country"]},
            },
            {"name": "other", "values": ["DE"], "outcome": APPROVED},
        ],
    },
]
SCORES = [
    {"requirement_id": "FRAUD-1.R1", "likelihood": 3, "impact": 3},
    {"requirement_id": "FRAUD-1.R2", "likelihood": 2, "impact": 2},
]

SINGLE = json.dumps(
    {"requirements": REQUIREMENTS, "gaps": GAPS, "conditions": CONDITIONS, "scores": SCORES}
)
ANALYST = json.dumps({"requirements": REQUIREMENTS, "gaps": GAPS})
DESIGNER = json.dumps({"conditions": CONDITIONS})
CRITIC = json.dumps({"findings": []})
PRIORITIZER = json.dumps({"scores": SCORES})

SCRIPTS = {
    Variant.SINGLE_PROMPT: [SINGLE],
    Variant.PIPELINE: [ANALYST, DESIGNER, PRIORITIZER],
    Variant.PIPELINE_WITH_CRITIC: [ANALYST, DESIGNER, CRITIC, PRIORITIZER],
}


def run(variant: Variant) -> tuple[TestDesign, FakeLLMClient]:
    client = FakeLLMClient(SCRIPTS[variant])
    return run_variant(variant, client, STORY, CONTEXT).value, client


def used_prompts(client: FakeLLMClient) -> list[str]:
    names = {
        load_prompt(name): name
        for name in (
            "single_prompt",
            "requirements_analyst",
            "test_designer",
            "critic",
            "risk_prioritizer",
        )
    }
    return [names[r.messages[0].content] for r in client.requests]


def test_the_variants_have_the_names_used_on_the_command_line() -> None:
    assert [v.value for v in Variant] == ["single-prompt", "pipeline", "pipeline-with-critic"]
    assert Variant("pipeline") is Variant.PIPELINE
    with pytest.raises(ValueError):
        Variant("pipeline-with-everything")


@pytest.mark.parametrize(
    ("variant", "calls"),
    [(Variant.SINGLE_PROMPT, 1), (Variant.PIPELINE, 3), (Variant.PIPELINE_WITH_CRITIC, 4)],
)
def test_each_variant_makes_its_own_number_of_model_calls(variant: Variant, calls: int) -> None:
    design, client = run(variant)

    assert isinstance(design, TestDesign)
    assert len(client.requests) == calls


def test_single_prompt_makes_one_call_with_the_single_prompt() -> None:
    _, client = run(Variant.SINGLE_PROMPT)

    assert used_prompts(client) == ["single_prompt"]


def test_pipeline_never_calls_the_critic() -> None:
    _, client = run(Variant.PIPELINE)

    assert used_prompts(client) == ["requirements_analyst", "test_designer", "risk_prioritizer"]


def test_pipeline_with_critic_calls_the_critic_once_when_the_first_review_is_clean() -> None:
    _, client = run(Variant.PIPELINE_WITH_CRITIC)

    assert used_prompts(client) == [
        "requirements_analyst",
        "test_designer",
        "critic",
        "risk_prioritizer",
    ]


def test_the_same_conditions_give_identical_test_cases_in_every_variant() -> None:
    designs = {variant: run(variant)[0] for variant in Variant}

    reference = designs[Variant.PIPELINE]
    assert len(reference.test_cases) == 7
    for design in designs.values():
        assert design.test_cases == reference.test_cases
        assert design.requirements == reference.requirements
        assert design.gaps == reference.gaps
        assert design.conditions == reference.conditions
        assert design.duplicate_ratio == reference.duplicate_ratio


@pytest.mark.parametrize("variant", list(Variant))
def test_every_variant_uses_the_same_request_settings(variant: Variant) -> None:
    client = FakeLLMClient(SCRIPTS[variant])

    run_variant(variant, client, STORY, CONTEXT, temperature=0.3, seed=9, num_ctx=4096)

    assert {(r.temperature, r.seed, r.num_ctx) for r in client.requests} == {(0.3, 9, 4096)}
