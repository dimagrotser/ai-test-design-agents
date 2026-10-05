# Oracle in Story vocabulary, SUT thresholds injected by the Binding

Expected Outcomes use Outcome Keys declared in the Test Context, not names from the SUT code. A hand-written Binding per target builds the SUT input from a Test Case and maps the SUT result back to an Expected Outcome. Nominal Input comes from the Test Context, so the model does not invent values for fields it is not testing.

Thresholds and lists (maximum amount, blocked countries, velocity limit) are not left to SUT defaults. The Binding builds an explicit `Rules` object from the SUT Config in the Corpus Manifest. This way the Story and the SUT cannot diverge silently. If the AC text and the Manifest disagree, the Gold Test Design fails its Validity Run before Eval Freeze.

## Consequences

Every new target needs a Binding and a Binding test. Some SUT constants cannot be injected, for example the currency list in `parse_transaction`. For those the Manifest records the expected value and the Gold Test Design's Validity Run checks it.
