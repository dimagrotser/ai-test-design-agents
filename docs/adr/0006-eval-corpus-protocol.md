# Eval corpus protocol

Stories are written by me as product owner. The README and DECISIONS prose of the SUT is a starting point, and I fix the thresholds and the inclusiveness of boundaries myself, because the prose states neither. Any divergence from the SUT surfaces in the Gold Validity Run before the freeze.

Everything the eval depends on is frozen with the tag `eval-freeze-v1` before any model run: Stories, Corpus Manifest, Test Context files, Gold Test Designs, Bindings, and the lists of Equivalent and Unreachable Mutants. A short changelog lists every edit made before the freeze. After the freeze, an Invalid Test Case caused by a Story mistake stays in the report.

The split is by target, so no semantics leak between parts. Held-out starts with two Stories, `parse_transaction` and `fraud.evaluate`, because they have the most boundaries. Dev holds `rules_from_env`, `render` and one Synthetic Story, a toy function with limits. Gap-probe Stories are a separate class and stay out of Kill Rate aggregates. Prompt tuning and Replay Fixture recording use Dev Stories only, so held-out data never reaches CI fixtures.

A Mutation Run only makes sense for targets under `src/payments/domain`, which is what mutmut mutates. That covers `parse_transaction`, `fraud.evaluate` and `rules_from_env`. `render` lives in `reporter/handler.py`, outside `domain/`, so it is never mutated, and the Synthetic Story is not in the SUT at all. Both get a Validity Run only.

Every Story except Gap-probe Stories gets a Gold Test Design, written from the Story before model runs and run through the same executor. It must have zero Invalid Test Cases, and for Stories with a Mutation Run its Kill Rate is the ceiling. The Baseline Suite of 33 SUT tests is the human reference. A Gold Test Design written from a Story can score below the Baseline Suite, and that result is published as it is.

The SUT is checked out by commit SHA, never by branch. The SHA is recorded in the Corpus Manifest and covered by Eval Freeze. CI on pull requests runs the Validity Run only. The Mutation Run stays local or in a manual job. If the SUT repository is private, tests that need it stay local.

## Consequences

With so few Stories the report shows per-Story numbers and makes no claim of statistical significance. This goes into the Limitations section of the README, together with the fact that Dev prompts are tuned partly on a Synthetic Story I wrote myself.
