# Oracle in Story vocabulary, SUT thresholds injected by the Binding

Expected Outcomes use Outcome Keys declared in the Test Context, not names from the SUT code. A hand-written Binding per target builds the SUT input from a Test Case and maps the SUT result back to an Expected Outcome. Nominal Input comes from the Test Context, so the model does not invent values for fields it is not testing.

Thresholds and lists (maximum amount, blocked countries, velocity limit) are not left to SUT defaults. The Binding builds an explicit `Rules` object from the SUT Config in the Corpus Manifest. This way the Story and the SUT cannot diverge silently. If the AC text and the Manifest disagree, the Gold Test Design fails its Validity Run before Eval Freeze.

Not every target returns a decision. `rules_from_env` returns a configuration and `render` returns text. For these, Expected Outcome has an optional `values` field: a map from name to a scalar of a closed set of types, compared by exact equality. The field is added to the schema together with the rest of Test Case in ticket 07 and stays unused until ticket 28, so the schema hash and the Replay Fixtures do not change when the first target needs it. `rules_from_env` needs no SUT Config, since the target is the configuration.

## Consequences

Every new target needs a Binding and a Binding test.

Because the Binding always injects explicit `Rules`, mutants on the SUT default thresholds cannot be killed through it. These are Unreachable Mutants. They are listed once, by hand, before Eval Freeze, and the frozen list is excluded from the denominator for every Variant. It is published next to the Equivalent Mutants and is not merged with them.

Some SUT constants cannot be injected at all, for example the currency list in `parse_transaction`. For those, the Gold Test Design includes a Test Case per list member, and any divergence between the Story and the SUT appears as an Invalid Test Case.
