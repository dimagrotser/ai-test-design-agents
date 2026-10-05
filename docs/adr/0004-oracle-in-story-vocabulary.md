# Oracle in Story vocabulary, SUT thresholds injected by the Binding

Expected Outcomes use Outcome Keys declared in the Test Context, not names from the SUT code. A hand-written Binding per target builds the SUT input from a Test Case and maps the SUT result back to an Expected Outcome. Nominal Input comes from the Test Context, so the model does not invent values for fields it is not testing.

Thresholds and lists (maximum amount, blocked countries, velocity limit) are not left to SUT defaults. The Binding builds an explicit `Rules` object from the SUT Config in the Corpus Manifest. This way the Story and the SUT cannot diverge silently. If the AC text and the Manifest disagree, the Gold Test Design fails its Validity Run before Eval Freeze.

## Consequences

Every new target needs a Binding and a Binding test.

Because the Binding always injects explicit `Rules`, mutants on the SUT default thresholds cannot be killed through it. These are Unreachable Mutants. They are listed once, by hand, before Eval Freeze, and the frozen list is excluded from the denominator for every Variant. It is published next to the Equivalent Mutants and is not merged with them.

Some SUT constants cannot be injected at all, for example the currency list in `parse_transaction`. For those, the Gold Test Design includes a Test Case per list member, and any divergence between the Story and the SUT appears as an Invalid Test Case.
