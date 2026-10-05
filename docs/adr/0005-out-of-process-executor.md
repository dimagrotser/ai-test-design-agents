# Out-of-process executor in the SUT environment

The SUT runs on Python 3.13 and this project runs on 3.12, so the SUT cannot be imported into our process. The executor runs Test Cases in a subprocess started with `uv run --project <SUT>`, with JSON on stdin and stdout. The Validity Run uses this runner and executes all Test Cases of a Story in one process. The Mutation Run copies the SUT to a temporary directory, adds a small pytest module generated from the valid Test Cases of the Validity Run, and runs mutmut on `src/payments/domain` there. The SUT repository is never modified.

The executor consumes structured Test Cases, not generated code. Kill Rate therefore measures the quality of the design and not the quality of code generation. Evaluating the Code Generator is a separate, deferred metric.

## Consequences

The Binding runs under the SUT's Python 3.13, so the Binding and the Test Case wire format must be stdlib-only, with no imports from this project and no pydantic. The alternative is to install those dependencies into the runner environment. The mutmut spike decides which one, and also confirms that mutmut works with Python 3.13 and that pytest is available in the SUT environment. Process start adds latency to every run, which is acceptable at this corpus size.
