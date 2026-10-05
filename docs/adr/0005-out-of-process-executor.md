# Out-of-process executor in the SUT environment

The SUT runs on Python 3.13 and this project runs on 3.12, so the SUT cannot be imported into our process. The executor runs Test Cases in a subprocess started with `uv run --project <SUT>`, with JSON on stdin and stdout. The Validity Run uses this runner. The Mutation Run copies the SUT to a temporary directory, adds a small pytest module generated from the frozen valid Test Cases, and runs mutmut on `src/payments/domain` there. The SUT repository is never modified.

The executor consumes structured Test Cases, not generated code. Kill Rate therefore measures the quality of the design and not the quality of code generation. Evaluating the Code Generator is a separate, deferred metric.

## Consequences

An early spike must confirm that mutmut works on the SUT with Python 3.13. Process start adds latency to every run, which is acceptable at this corpus size.
