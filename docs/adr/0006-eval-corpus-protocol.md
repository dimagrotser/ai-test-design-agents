# Eval corpus protocol

Stories are written by me from the README and DECISIONS prose of the SUT, not from its code, and are frozen with the tag `eval-freeze-v1` before any model run. A short changelog lists every edit made before the freeze. After the freeze, an Invalid Test Case caused by a Story mistake stays in the report.

The split is by target, so no semantics leak between parts. Held-out starts with two Stories, `parse_transaction` and `fraud.evaluate`, because they have the most boundaries. Dev holds `rules_from_env`, `render` and one Synthetic Story, a toy function with limits that gets a Validity Run only. Gap-probe Stories are a separate class and stay out of Kill Rate aggregates. Prompt tuning and Replay Fixture recording use Dev Stories only, so held-out data never reaches CI fixtures.

Every Story gets a Gold Test Design, written from the Story before model runs and run through the same executor. It must have zero Invalid Test Cases, and its Kill Rate is the ceiling for that Story. The Baseline Suite of 33 SUT tests is the human reference. A Gold Test Design written from a Story can score below the Baseline Suite, and that result is published as it is.

## Consequences

With so few Stories the report shows per-Story numbers and makes no claim of statistical significance. This goes into the Limitations section of the README, together with the fact that Dev prompts are tuned partly on a Synthetic Story I wrote myself.
