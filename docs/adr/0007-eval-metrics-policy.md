# Eval metrics policy

Equivalent Mutants are reviewed once, by hand, before Eval Freeze. Candidates are mutants that survive both the Gold Test Design and the Baseline Suite. The frozen list, together with the Unreachable Mutants from ADR 0004, is removed from the denominator for every Variant and does not change afterward. A mutant that survives the Gold Test Design but is killed by the Baseline Suite is not a candidate, since it shows where Gold is weaker than human tests. A timeout counts as killed and is reported in its own column. An uncovered mutant counts as survived.

Three Variants are compared: Single Prompt, Pipeline, and Pipeline with Critic, so that the effect of the Critic is isolated. Each cell (Variant, model, Story) is repeated with temperature 0.3 and varied seeds, because repeats at temperature 0 with a fixed seed carry no information about variance. Temperature 0 is used only when recording Replay Fixtures. The report publishes the mean and the range over repeats. Cloud runs use one repeat and are marked as such. Tokens and wall-clock time per Story are reported alongside Kill Rate and AC Coverage. A Story whose Structured Generation fails counts as zero coverage and zero kills, and the Failure Rate and Invalid Rate are reported next to the results.

The size of the matrix is fixed only after one timed Dev run of the ~30B model on the local machine.

## Consequences

Replay-based CI checks pipeline wiring, not model quality, and the README must say that.
