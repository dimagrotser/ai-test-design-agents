from atda.schemas.requirements import Analysis, Gap, Requirement


def test_a_gap_without_an_ac_refers_to_the_whole_story() -> None:
    gap = Gap(text="The currency of the limit is not stated.")

    assert gap.ac_id is None


def test_an_analysis_survives_a_json_round_trip() -> None:
    analysis = Analysis(
        requirements=(
            Requirement(id="S-1.R1", ac_id="AC-1", text="Amounts over 10000 are rejected."),
        ),
        gaps=(Gap(ac_id="AC-1", text="Is 10000 itself allowed?"), Gap(text="Currency unknown.")),
    )

    assert Analysis.model_validate_json(analysis.model_dump_json()) == analysis
