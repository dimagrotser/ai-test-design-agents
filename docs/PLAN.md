# Plan

Tickets for ai-test-design-agents. Vocabulary is in `CONTEXT.md`, decisions are in `docs/adr/`.

One ticket is one branch and one PR that can be reviewed by eye in 15-20 minutes. Tickets are vertical slices: each one leaves something that runs or can be checked on its own.

## How to read this file

- **Owner**: `agent` tickets are implemented by the coding agent. `maintainer` tickets are written by hand by the repo owner. The agent never drafts Stories, Test Context files, Gold Test Designs, the Corpus Manifest or the mutant lists.
- **Status**: `todo` or `done`. The maintainer sets `done` after merging the PR.
- **Picking the next ticket**: skip `maintainer` tickets, take the first `agent` ticket with status `todo` whose blockers are all `done`, and report which `maintainer` tickets are blocking or about to block the frontier. Optional tickets (38, 39) are never picked unless named.
- **Definition of done**, for every ticket with a branch: the failing tests were written first, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy src` pass, the PR stays inside the ticket, and unrelated problems are listed in the PR description.
- Tests never call a real model or the network. Tests that need the SUT checkout are marked `sut` and skipped when the SUT path is not configured.

## Ship points

1. **Scaffold through Test Designer on one Story, with CI** (17 tickets: 15 agent and 2 maintainer, including spike 02, which runs in parallel and blocks nothing here). `design` runs on the Synthetic Story through Replay Fixtures in CI and writes a Test Design report. The repository is presentable here.
2. **Walking skeleton, no LLM** (6 more tickets, 23 in total; spike 02 is counted in ship point 1). A hand-written Gold Test Design for FRAUD goes through the Binding, the Validity Run and mutmut to a Kill Rate, shown next to the Baseline Suite of 33 SUT tests.
3. **Full eval** (23 more tickets, 46 in total, of which 2 are optional). Three Variants, three local models and one cloud model, the frozen corpus, the report and the README with results.

## Ticket index

| id | title | owner | blocked by |
|---|---|---|---|
| 01 | Scaffold and CI | agent | none |
| 01a | LLMClient port and import-rule test | agent | 01 |
| 02 | Spike: mutmut and pytest in the SUT environment | agent | 01 |
| 03 | Story, Test Context and FileSource | agent | 01a |
| 04 | `design` command skeleton | agent | 03 |
| 05 | Structured Generation and FakeLLMClient | agent | 01a |
| M1 | Synthetic Story and its Test Context | maintainer | 03 |
| 06 | Requirements Analyst | agent | 04, 05 |
| 07 | Test Condition schema and EP/BVA expansion | agent | 06 |
| 08 | Test Designer agent with evidence check | agent | 07 |
| 09 | Decision Table expansion and duplicate merge | agent | 07 |
| 10 | Test Design report | agent | 08 |
| 11 | Ollama setup (checklist, no PR) | maintainer | none |
| 12 | OllamaClient and `post_json` | agent | 05, 11 |
| 12a | Provider Profiles | agent | 12 |
| 13 | ReplayClient, fixture key and `record` | agent | 08, 09, 12a, M1 |
| 14 | README for ship point 1 | agent | 10, 13 |
| 15 | Corpus Manifest loader | agent | 03 |
| M2 | FRAUD Story, Test Context, SUT Config, Gold Test Design | maintainer | 09, 15 |
| 16 | fraud.evaluate Binding and Validity Run | agent | 02, 04, 15, M2 |
| 17 | Mutation Run and Kill Rate | agent | 16 |
| 18 | Baseline Suite comparison and AC Coverage | agent | 17 |
| 19 | README for ship point 2 | agent | 18 |
| 20 | Risk Prioritizer | agent | 06 |
| 21 | Deterministic Findings | agent | 09 |
| 22 | Critic and Refinement Loop | agent | 08, 21 |
| 23 | Variants | agent | 20, 22 |
| 24 | OpenAI-compatible client | agent | 12a |
| 25 | AnthropicClient (untested) | agent | 12a |
| 26 | JiraSource stub | agent | 03 |
| M3 | Stories and Test Contexts for the remaining targets | maintainer | 15 |
| 27 | parse_transaction Binding | agent | 16, M3 |
| 28 | rules_from_env Binding | agent | 16, M3 |
| 29 | render Binding | agent | 16, M3 |
| 30 | Synthetic target and Binding | agent | 16, M1 |
| M4 | Gold Test Designs for the remaining Stories | maintainer | 27, 28, 29, 30 |
| 31 | Eval metrics and aggregation | agent | 18 |
| 32 | Prompt tuning on Dev Stories | agent | 13, 23, 28, 29, 30, 31 |
| 33 | Spike: wall-clock of one Dev run on the ~30B model | agent | 11, 12a, 23 |
| 34 | Eval matrix runner | agent | 23, 31, 33 |
| 35 | Eval report | agent | 34 |
| M5 | Eval Freeze | maintainer | 18, M4, 32, 33 |
| 36 | Held-out eval runs | agent | 24, 35, M5 |
| 37 | README with results and Limitations | agent | 36 |
| 38 | Optional: one chart | agent | 37 |
| 39 | Optional: corpus expansion | maintainer | 37 |

---

# Ship point 1: scaffold through Test Designer on one Story

### 01: Scaffold and CI

- **Status:** done
- **Owner:** agent
- **Branch:** chore/scaffold
- **Blocked by:** none
- **Goal:** An empty package that installs, lints, type-checks and tests green locally and in CI.
- **Scope:** `pyproject.toml` for Python 3.12 with pinned pydantic, pyyaml, pytest, ruff and mypy. `src/atda/` with an empty package. Ruff config. `mypy --strict` on `src/`. One smoke test. GitHub Actions workflow with jobs lint, typecheck and tests, run in that order. `uv.lock`. A README stub of one paragraph.
- **Out of scope:** Any domain code, ports, mutmut, README content beyond the stub.
- **Acceptance criteria:**
  - [ ] On a fresh clone, `uv sync && uv run pytest` passes.
  - [ ] The workflow runs lint, then typecheck, then tests, and fails if any step fails.
  - [ ] Mypy strict applies to `src/` only.
  - [ ] All dependency versions are pinned.
- **Tests first:** `atda` imports. The workflow is checked by opening the PR.

### 01a: LLMClient port and import-rule test

- **Status:** done
- **Owner:** agent
- **Branch:** feat/llm-port-import-rule
- **Blocked by:** 01
- **Goal:** ADR 0001 is enforced mechanically before the first adapter exists.
- **Scope:** `LLMClient` as a `typing.Protocol`, with `LLMRequest` (messages, optional JSON schema, temperature, seed, context size) and `LLMResponse` (text, input and output token counts) as Pydantic models. A test that parses the modules under `src/atda/` outside `adapters/` and fails on any import from `atda.adapters`.
- **Out of scope:** `RequirementsSource` (ticket 03), any adapter, FakeLLMClient (ticket 05).
- **Acceptance criteria:**
  - [ ] The import-rule test passes on the real tree.
  - [ ] The same check fails on a temporary tree where a core module imports from `adapters/`.
  - [ ] The checker handles `import x` and `from x import y` forms.
- **Tests first:** A violating temporary package is reported with file and line. A clean package is accepted. The real tree is clean.

### 02: Spike: mutmut and pytest in the SUT environment

- **Status:** done
- **Owner:** agent
- **Branch:** chore/spike-mutmut-sut
- **Blocked by:** 01
- **Goal:** Answer the open questions of ADR 0005 before any Binding or Mutation Run code is written. Runs in parallel with ship point 1.
- **Scope:** On a copy of the SUT, check that `uv run --project` works with its Python 3.13, that pytest is available in the SUT environment, that mutmut runs on `src/payments/domain` against the 33 existing unit tests, how long a full run takes, how many mutants each target file produces, and whether mutmut can be limited to chosen functions. Check that importing `payments.reporter.handler` has no side effects. Decide whether the Binding and the Test Case wire format are stdlib-only or whether dependencies are installed into the runner environment. Write the findings to `docs/spikes/mutmut-sut.md` and amend ADR 0005 if the decision changes it.
- **Out of scope:** Binding code, Mutation Run code, any change to the SUT repository.
- **Acceptance criteria:**
  - [ ] The note answers each question above with the command used and the output that supports it.
  - [ ] The stdlib-only decision is stated in one sentence.
  - [ ] The SUT repository has no changes (`git status` clean there).
- **Tests first:** None. The acceptance criteria are the checks.

### 03: Story, Test Context and FileSource

- **Status:** done
- **Owner:** agent
- **Branch:** feat/story-file-source
- **Blocked by:** 01a
- **Goal:** A Story and its Test Context can be loaded from files into typed models.
- **Scope:** `Story` model (id, title, text, Acceptance Criteria with ids). Parser for front matter with `id` and `title`, free text, and a `## Acceptance criteria` section with `- AC-n: ...` lines. `TestContext` model (target, Nominal Input, Outcome Keys) loaded from YAML. `RequirementsSource` as a `typing.Protocol`. `FileSource` in `adapters/`.
- **Out of scope:** Corpus Manifest, GitHubIssuesSource, JiraSource, the CLI.
- **Acceptance criteria:**
  - [ ] A valid Story file yields a `Story` with every AC and its id.
  - [ ] Duplicate AC ids, a missing `## Acceptance criteria` section and a missing `id` each fail with a message that names the file and the problem.
  - [ ] A Test Context without a target or without Outcome Keys is rejected.
  - [ ] `FileSource` satisfies `RequirementsSource` under mypy.
- **Tests first:** Parsing of front matter and AC lines. Each rejection case. Protocol conformance.

### 04: `design` command skeleton

- **Status:** done
- **Owner:** agent
- **Branch:** feat/cli-design
- **Blocked by:** 03
- **Goal:** `design` exists as an argparse command that loads and validates its inputs, so later tickets only add pipeline stages.
- **Scope:** Entry point with an argparse subcommand `design <story> --context <file>`. It loads both files through `FileSource` and prints the validated inputs as JSON. Exit code 2 and a one-line message on invalid input.
- **Out of scope:** Agents, LLM selection flags, `eval` and `record` subcommands.
- **Acceptance criteria:**
  - [ ] `uv run <entry point> design story.md --context ctx.yaml` prints JSON for valid files.
  - [ ] Invalid input exits with 2 and prints the cause on stderr.
- **Tests first:** Valid run returns exit 0 and parseable JSON. Missing file, bad Story and bad Test Context each return exit 2.

### 05: Structured Generation and FakeLLMClient

- **Status:** done
- **Owner:** agent
- **Branch:** feat/structured-generation
- **Blocked by:** 01a
- **Goal:** One call that returns a validated Pydantic model from an LLM, with bounded retries.
- **Scope:** A `generate` function that takes a client, a request, a model type and a maximum number of attempts. On a validation or JSON error it retries with the error text appended to the prompt. After the last attempt it raises `StructuredGenerationError` carrying the history of every attempt (raw text and error). `FakeLLMClient` with scripted responses that records the requests it received. Token counts are summed over attempts.
- **Out of scope:** Real adapters, passing the JSON schema to a provider, semantic checks beyond Pydantic validators.
- **Acceptance criteria:**
  - [ ] A valid first response returns the model with one attempt.
  - [ ] A failing response is retried and the second request contains the error text.
  - [ ] After the maximum number of attempts the exception contains all attempts in order.
  - [ ] Output that is not JSON counts as a failed attempt.
- **Tests first:** Each criterion above, plus summed token counts.

### M1: Synthetic Story and its Test Context

- **Status:** todo
- **Owner:** maintainer
- **Branch:** chore/corpus-synthetic
- **Blocked by:** 03
- **Goal:** The Dev Story used for ship point 1 and for recording the first Replay Fixtures.
- **Scope:** One Synthetic Story about a payments-flavoured toy function, a fee depending on amount and card type. 3 or 4 ACs that give the Test Designer material for EP, BVA and a Decision Table. The Test Context file with target, Nominal Input and Outcome Keys. Both files go under `eval/corpus/`.
- **Out of scope:** The toy function itself (ticket 30), the Manifest entry (M2), a Gold Test Design (M4).
- **Acceptance criteria:**
  - [ ] Both files load through `FileSource`.
  - [ ] Every AC has an id and states its thresholds and boundary inclusiveness.
- **Tests first:** None. Ticket 03 loads the files.

### 06: Requirements Analyst

- **Status:** done
- **Owner:** agent
- **Branch:** feat/requirements-analyst
- **Blocked by:** 04, 05
- **Goal:** `design` turns a Story into Requirements and Gaps, with stable ids assigned by code.
- **Scope:** `Requirement` and `Gap` models. An `analyze` function that asks the model, through Structured Generation, for requirement texts linked to AC ids and for Gaps. Code assigns Requirement ids (`<story id>.R<n>`, in order). A response that names an unknown AC id fails validation and is retried with the error text. The prompt is a separate file. The pipeline function and the `design` output include Requirements and Gaps.
- **Out of scope:** Selecting a real client from the CLI (tickets 12 and 13), Test Conditions, risk scores.
- **Acceptance criteria:**
  - [ ] Requirement ids are unique, stable across reruns of the same response, and assigned by code.
  - [ ] A Requirement that links to a non-existent AC is rejected and retried.
  - [ ] One AC may produce several Requirements.
  - [ ] A Gap may refer to the Story or to an AC.
- **Tests first:** Id assignment from a scripted response. Unknown AC id triggers a retry with the error in the prompt. One AC to many Requirements. Gap reference validation.

### 07: Test Condition schema and EP/BVA expansion

- **Status:** done
- **Owner:** agent
- **Branch:** feat/test-conditions-ep-bva
- **Blocked by:** 06
- **Goal:** Deterministic expansion from Test Conditions to Test Cases for EP and BVA, with no LLM involved (ADR 0002).
- **Scope:** `TestCondition`, `TestCase` and `TestDesign` models. A BVA condition has a field, a boundary, an operator from a closed enum and Expected Outcomes on each side, plus a verbatim evidence quote. An EP condition has classes with Expected Outcomes. Expansion code: three BVA points around a boundary with a step by type (`Decimal` 0.01, `int` 1), EP representatives (every member of a small enumerated class, otherwise the given representative), overrides merged onto the Nominal Input. Every Test Case records its Technique, a rationale and its Requirement and AC links. Expected Outcome has the optional `values` field from ADR 0004 (name to scalar, closed set of types, exact equality). It is part of the schema now and unused until ticket 28, so the schema and the Replay Fixtures stay stable.
- **Out of scope:** Decision Table, duplicate merge, the LLM agent, the evidence check against the Story text, any use of `values`.
- **Acceptance criteria:**
  - [ ] A `>` boundary at 10000 expands to 9999.99, 10000 and 10000.01 with the outcomes the operator implies.
  - [ ] A `>=` boundary at 5 expands to 4, 5 and 6.
  - [ ] An enumerated class of three members plus one other class gives four Test Cases.
  - [ ] Output order and ids are deterministic.
  - [ ] A condition with no operator is rejected by the schema.
  - [ ] An Expected Outcome without `values` is valid, and `values` accepts only the closed set of scalar types.
- **Tests first:** One table-driven test per operator. EP enumeration. Determinism. Schema rejection. Accepted and rejected types for `values`.

### 08: Test Designer agent with evidence check

- **Status:** done
- **Owner:** agent
- **Branch:** feat/test-designer
- **Blocked by:** 07
- **Goal:** `design` now produces a Test Design from a Story: the model extracts Test Conditions and code expands them.
- **Scope:** A `design_tests` function that asks the model for Test Conditions per Requirement through Structured Generation. Code checks that each evidence quote is a substring of the AC text and that every Expected Outcome uses an Outcome Key from the Test Context. A failed check is retried with the error text. Expansion comes from ticket 07. The prompt is a separate file. The `design` output includes the Test Design.
- **Out of scope:** Decision Table, risk scores, the Critic, a real client.
- **Acceptance criteria:**
  - [ ] Evidence that does not occur in the AC text is rejected and retried.
  - [ ] An Outcome Key outside the Test Context is rejected and retried.
  - [ ] A scripted valid response yields the expected Test Cases through the whole pipeline.
  - [ ] A Gap from the Analyst is carried into the Test Design unchanged.
- **Tests first:** Evidence mismatch. Unknown Outcome Key. End-to-end with a scripted BVA condition. Gap pass-through.

### 09: Decision Table expansion and duplicate merge

- **Status:** done
- **Owner:** agent
- **Branch:** feat/decision-table-merge
- **Blocked by:** 07
- **Goal:** Decision Table cases and the Duplicate Ratio, measured before duplicates are merged (ADR 0007).
- **Scope:** Decision Table condition (up to four boolean conditions, outcome as the union of Outcome Keys). A row sets an input to the boundary point that breaks its rule and leaves every other input at its Nominal value; the values come from the related BVA and EP conditions. Normalized input for comparison (Decimal normalized, sets sorted). Duplicate Ratio computed before merge and stored on the Test Design. Exact duplicates merge into one Test Case with several Requirement and AC links. Two Test Cases with the same input and different outcomes are not merged and are returned as Contradictions.
- **Out of scope:** Turning Contradictions into Findings (ticket 21), semantic redundancy.
- **Acceptance criteria:**
  - [ ] A row of a three-condition table with a single broken rule merges with the matching BVA case, and the merged case keeps both Requirement links.
  - [ ] Duplicate Ratio equals one minus unique over total, taken before the merge.
  - [ ] `Decimal("10000.0")` and `Decimal("10000")` count as the same input.
  - [ ] A Contradiction is reported and both cases are kept.
  - [ ] More than four conditions are rejected.
- **Tests first:** The all-false row merge. The ratio arithmetic. Normalization. Contradiction. The condition limit.

### 10: Test Design report

- **Status:** done
- **Owner:** agent
- **Branch:** feat/design-report
- **Blocked by:** 08
- **Goal:** `design --out <dir>` writes the Test Design as JSON and as a Markdown report with traceability.
- **Scope:** `test-design.json` as the canonical artifact. `test-design.md` with Requirements, Gaps, Test Cases, and a matrix from AC to Requirement to Test Case. Both files are produced by code, with no LLM.
- **Out of scope:** Priorities (ticket 20), other formats, TMS export.
- **Acceptance criteria:**
  - [ ] The JSON loads back into `TestDesign` without change.
  - [ ] The matrix lists every AC, and an AC without Test Cases is marked as uncovered.
  - [ ] The output is byte-identical for the same input.
- **Tests first:** JSON round trip. An uncovered AC in the matrix. Golden Markdown file.

### 11: Ollama setup (checklist, no PR)

- **Status:** todo
- **Owner:** maintainer
- **Branch:** none
- **Blocked by:** none
- **Goal:** Ollama runs locally with one model of each size, so the first recording can happen.
- **Scope:** Install Ollama. Pull one model of about 8B, one of about 14B and one of about 30B (a MoE model in Q4 fits 32 GB). Run one request against `/api/chat` with a JSON schema in `format` and confirm that the response follows it. Note the exact tags and quantization.
- **Out of scope:** Choosing the final models (settled at Eval Freeze, M5).
- **Acceptance criteria:**
  - [ ] `ollama list` shows three models.
  - [ ] A schema-constrained request returns valid JSON for each model.
  - [ ] The tags are pasted into the PR description of ticket 12.
- **Tests first:** None.

### 12: OllamaClient and `post_json`

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/ollama-client
- **Blocked by:** 05, 11
- **Goal:** `design --ollama <model>` runs the pipeline against a local model.
- **Scope:** A shared `post_json` helper over `urllib` with a timeout and a custom User-Agent. `OllamaClient` maps `LLMRequest` to `/api/chat` with the schema in `format` and temperature, seed and `num_ctx` in `options`. It reads token counts from the response and raises typed errors on HTTP failures and timeouts. `design` gets the `--ollama` option.
- **Out of scope:** Replay, cloud clients, any real network call in tests.
- **Acceptance criteria:**
  - [ ] The payload contains the schema, temperature, seed and `num_ctx`.
  - [ ] Prompt and output token counts are mapped to `LLMResponse`.
  - [ ] Non-200 responses and timeouts raise distinct errors.
  - [ ] Every request carries the custom User-Agent.
- **Tests first:** All four, with the transport function stubbed.

### 12a: Provider Profiles

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/provider-profiles
- **Blocked by:** 12
- **Goal:** Models are chosen by a named Provider Profile, so the eval and Eval Freeze have one thing to pin.
- **Scope:** A `ProviderProfile` model: adapter, endpoint, model tag, structured-output mechanism (a closed set of names defined by the adapters), context size, timeout, local or cloud, and the name of the environment variable that holds the key for cloud profiles. Profile files in the repo, with one profile per local model (about 8B, 14B and 30B, using the tags from checklist 11). A `--profile <name>` option on `design` and `record` that replaces `--ollama`.
- **Out of scope:** Cloud profiles (tickets 24 and 25), choosing the final models (M5).
- **Acceptance criteria:**
  - [ ] An unknown profile name fails and lists the available names.
  - [ ] A profile with a missing field, or with a field that holds a key value instead of a variable name, is rejected.
  - [ ] `design --profile <name>` builds the matching client.
  - [ ] The three local profiles load.
- **Tests first:** Valid profile loads. Each rejection. Client construction from a profile with the transport stubbed.

### 13: ReplayClient, fixture key and `record`

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/replay-record
- **Blocked by:** 08, 09, 12a, M1
- **Goal:** CI runs the whole pipeline on the Synthetic Story from recorded responses, with no model and no keys.
- **Scope:** Fixture key as a hash of model, messages, schema, temperature, seed and `num_ctx`. `ReplayClient` reads fixtures by key and raises a clear error that shows the key when none matches. A `record --profile <name>` subcommand runs the pipeline with a real client at temperature 0 and writes fixtures. A fixture stores the request body and the response body only, never headers, keys or tokens. The maintainer records the fixtures locally from the Synthetic Story and commits them in this PR. A CI step runs `design` on that Story through Replay and compares the output with an expected Test Design.
- **Out of scope:** Any recording in CI. `record` takes a Story from the Corpus Manifest and calls `require_dev` from ticket 15 before it does anything else.
- **Acceptance criteria:**
  - [ ] Changing any one of the six key components changes the key.
  - [ ] A changed prompt makes the replay fail with a missing-fixture error, not a silent old answer.
  - [ ] Replaying recorded fixtures reproduces the recorded Test Design exactly.
  - [ ] A recorded fixture file contains no authorization header and no key value.
  - [ ] `record` on a held-out Story exits non-zero and writes nothing.
  - [ ] The CI step runs and passes.
- **Tests first:** Key sensitivity, parametrized over the six components. Missing fixture error. Record then replay gives the same result, using FakeLLMClient as the recorded source. A recording made with a request that carries a fake key and an authorization header leaves neither in the file.

### 14: README for ship point 1

- **Status:** todo
- **Owner:** agent
- **Branch:** chore/readme-ship-1
- **Blocked by:** 10, 13
- **Goal:** The repository can be understood and run by a stranger.
- **Scope:** What the project does, the architecture in a few paragraphs (ports and adapters, the import rule, deterministic expansion), real commands for install, tests and `design` on the Synthetic Story, a table of what is implemented, a stub (`JiraSource`) or untested (`AnthropicClient`) and what is planned. A sentence that replay-based CI checks pipeline wiring, not model quality. A short Limitations section. Dry technical prose.
- **Out of scope:** Eval results.
- **Acceptance criteria:**
  - [ ] Every command in the README was run and works.
  - [ ] The replay statement and the Limitations section are present.
  - [ ] No em-dashes and none of the banned marketing words.
- **Tests first:** None.

> **Cut line: ship point 1.** 17 tickets (15 agent, 2 maintainer), including spike 02 and Provider Profiles. If the project stops here, it is a working Story to Test Design tool with CI on replayed responses.

---

# Ship point 2: walking skeleton, no LLM

### 15: Corpus Manifest loader

- **Status:** done
- **Owner:** agent
- **Branch:** feat/corpus-manifest
- **Blocked by:** 03
- **Goal:** Eval-only data is kept apart from what the agents see (ADR 0008).
- **Scope:** `CorpusManifest` model: per Story the Test Context file, SUT Config, split (dev or held-out) and class (normal or Gap-probe), plus the SUT commit SHA, which must be a full SHA and never a branch name. A function that returns the agent view of a Story, containing the Story and its Test Context only. A guard, `require_dev`, that refuses held-out Stories, for the `record` command of ticket 13 to call.
- **Out of scope:** Manifest content (M2, M3), the eval commands.
- **Acceptance criteria:**
  - [ ] The agent view has no field for SUT Config, split or class.
  - [ ] A missing Test Context file, an unknown split or an unknown class is rejected with a clear message.
  - [ ] A SUT reference that is not a full commit SHA, such as `main` or an abbreviated hash, is rejected.
  - [ ] `require_dev` refuses a held-out Story and an unknown id, and accepts a dev Story.
- **Tests first:** Valid manifest. Each rejection, including the branch name as SUT reference. The agent view type check. The `require_dev` guard.

### M2: FRAUD Story, Test Context, SUT Config, Gold Test Design

- **Status:** todo
- **Owner:** maintainer
- **Branch:** chore/corpus-fraud
- **Blocked by:** 09, 15
- **Goal:** The first held-out Story and its oracle.
- **Scope:** The FRAUD Story for `fraud.evaluate`, written as product owner with thresholds and boundary inclusiveness fixed. It stays silent about currency, so that this surfaces as a Gap (see "Flagged ambiguities" in `CONTEXT.md`). The Test Context file. The SUT Config. A Gold Test Design as `TestDesign` JSON, written from the Story and not from code. Manifest entries for FRAUD and for the Synthetic Story, with the SUT commit SHA. A file `docs/eval-changelog.md` with the first line for pre-freeze edits.
- **Out of scope:** The Binding (ticket 16), any model run.
- **Acceptance criteria:**
  - [ ] The Gold Test Design loads as `TestDesign`.
  - [ ] The Manifest loads and both Stories appear in it.
- **Tests first:** None. Tickets 15 and 16 load and run the files.

### 16: fraud.evaluate Binding and Validity Run

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/validity-run-fraud
- **Blocked by:** 02, 04, 15, M2
- **Goal:** The Gold Test Design for FRAUD runs against the unmodified SUT and every Test Case passes (ADRs 0004 and 0005).
- **Scope:** A Binding for `fraud.evaluate` under `eval/bindings/`, shaped by the spike decision. It builds an explicit `Rules` object from the SUT Config and maps `Decision.reasons` to Outcome Keys. The runner is started with `uv run --project <SUT>`, reads Test Cases as JSON on stdin and writes actual outcomes as JSON on stdout, and runs all Test Cases of a Story in one process. An `eval validity` subcommand reports passed and Invalid Test Cases per Story. The SUT path comes from an option or an environment variable. Unit tests for the Binding. A CI job that checks out `event-driven-payments` at the SHA from the Corpus Manifest and runs the Validity Run, and nothing heavier, on pull requests. If the SUT repository is private, the job is left out and the `sut` tests stay local.
- **Out of scope:** Mutation Run, the other targets, any CI job that runs mutmut.
- **Acceptance criteria:**
  - [ ] The Gold Test Design for FRAUD has zero Invalid Test Cases.
  - [ ] A design with a wrong operator on the amount boundary reports an Invalid Test Case at 10000.
  - [ ] The Binding injects thresholds from the SUT Config and never uses SUT defaults.
  - [ ] The SUT repository is not modified.
  - [ ] CI checks out the SUT by the pinned SHA, or the PR says why the job is absent.
- **Tests first:** Mapping of each reason text to its Outcome Key, including several reasons at once. Threshold injection. An unknown reason text fails loudly. A `sut` test with the real checkout for the wrong-operator case.

### 17: Mutation Run and Kill Rate

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/mutation-run
- **Blocked by:** 16
- **Goal:** Valid Test Cases of a Test Design are scored by mutmut on a copy of the SUT.
- **Scope:** Copy the SUT to a temporary directory. Generate a pytest module from the valid Test Cases of the Validity Run that calls the same Binding. Run mutmut on `src/payments/domain`. Parse the result. Statuses: killed, survived, timeout (counted as killed and shown in its own column), not covered (counted as survived). Kill Rate excludes the Equivalent and Unreachable Mutants from the denominator. `eval mutation` prints the result as JSON. The Mutation Run runs locally or in a manual `workflow_dispatch` job and never on pull requests.
- **Out of scope:** Baseline Suite, the mutant lists themselves, any model run, running mutmut on pull requests.
- **Acceptance criteria:**
  - [ ] The Kill Rate for the FRAUD Gold Test Design is produced end to end.
  - [ ] The timeout column and the counts of excluded mutants are in the output.
  - [ ] Invalid Test Cases are not part of the generated pytest module.
  - [ ] After the run the SUT repository is unchanged.
- **Tests first:** Parsing of recorded mutmut output into statuses. Kill Rate arithmetic with timeouts and exclusions. The Invalid Test Case filter. A `sut` test for the end-to-end run.

### 18: Baseline Suite comparison and AC Coverage

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/baseline-comparison
- **Blocked by:** 17
- **Goal:** One table shows Kill Rate for the Gold Test Design next to the Baseline Suite of 33 tests, always with AC Coverage (ADRs 0006 and 0007).
- **Scope:** Run the 33 SUT unit tests through the same mutant set and denominator. AC Coverage as a function over a Test Design. Output of Kill Rate, AC Coverage, the Gold ceiling and the Baseline value together. A list of candidates for Equivalent Mutants: mutants that survive both Gold and Baseline. A loader for the two frozen mutant lists, which may be empty until M5.
- **Out of scope:** Deciding which candidates are equivalent (M5).
- **Acceptance criteria:**
  - [ ] The table has Gold and Baseline Kill Rate for FRAUD on the same denominator.
  - [ ] Kill Rate is never printed without AC Coverage.
  - [ ] A mutant killed by the Baseline Suite but not by Gold is not listed as a candidate.
- **Tests first:** Candidate selection from synthetic results. Same-denominator check. The output refuses to print Kill Rate alone.

### 19: README for ship point 2

- **Status:** todo
- **Owner:** agent
- **Branch:** chore/readme-ship-2
- **Blocked by:** 18
- **Goal:** The README shows the skeleton result honestly.
- **Scope:** The Gold and Baseline table for FRAUD, the commands to reproduce it, and how the Binding, Validity Run and Mutation Run fit together. Update Limitations.
- **Out of scope:** Model results.
- **Acceptance criteria:**
  - [ ] The numbers in the README match a run that was done for this PR.
  - [ ] If Gold scores below the Baseline Suite, the README says so.
- **Tests first:** None.

> **Cut line: ship point 2.** 6 more tickets, 23 in total. If the project stops here, it can measure a Test Design against mutants of the SUT, with no model comparison.

---

# Ship point 3: full eval

### 20: Risk Prioritizer

- **Status:** done
- **Owner:** agent
- **Branch:** feat/risk-prioritizer
- **Blocked by:** 06
- **Goal:** Test Cases carry a Priority derived from risk.
- **Scope:** The model scores likelihood and impact from 1 to 3 for each Requirement through Structured Generation. Code maps the pair to a Priority with an explicit 3 by 3 lookup table, not a formula. The table is: P1 for likelihood times impact of 6 or 9, P2 for 3 or 4, and P3 for 1 or 2, written out cell by cell. A Test Case takes the highest Priority of its Requirements. The report gets a Priority column.
- **Out of scope:** Using Priority to order or filter Test Cases.
- **Acceptance criteria:**
  - [ ] Each of the nine likelihood and impact cells maps to its Priority through the lookup table.
  - [ ] A merged Test Case takes the highest Priority of its Requirements.
  - [ ] A score outside 1 to 3 is rejected and retried.
- **Tests first:** One test per table cell, nine in all. Merged inheritance. Out-of-range retry.

### 21: Deterministic Findings

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/deterministic-findings
- **Blocked by:** 09
- **Goal:** Code reports coverage, traceability, duplicates and operator problems as typed Findings.
- **Scope:** `Finding` model with type, severity and a reference. Checks for missing coverage of an AC or a Requirement, untraceable Test Cases, duplicates, Contradictions (blocking), and a deterministic operator check from a phrase lexicon (for example "over" and "exceeds" against `>`, "at least" and "or more" against `>=`) that warns when the chosen operator disagrees with the wording.
- **Out of scope:** The LLM Critic, the loop.
- **Acceptance criteria:**
  - [ ] Each check has at least one passing and one failing case.
  - [ ] Contradictions are blocking, the others are not.
  - [ ] The lexicon is data, and adding a phrase needs no code change.
- **Tests first:** Table-driven phrases against operators. Coverage gap. Untraceable case. Severity of each type.

### 22: Critic and Refinement Loop

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/critic-loop
- **Blocked by:** 08, 21
- **Goal:** Blocking Findings send the Test Designer back for another attempt, at most twice (ADR 0003).
- **Scope:** A Critic agent for the semantic Finding types (wrong technique, vague expected result). A loop that merges deterministic and Critic Findings, passes blocking ones to the Test Designer only, and stops when none are left or after two iterations. The Analyst is never rerun.
- **Out of scope:** Selecting Variants (ticket 23).
- **Acceptance criteria:**
  - [ ] The loop stops after two iterations even if blocking Findings remain.
  - [ ] The Analyst is called once per Story.
  - [ ] Requirement ids are identical before and after the loop.
  - [ ] Finding text reaches the Designer prompt.
- **Tests first:** Iteration limit. One analyst call. Id stability. Prompt content.

### 23: Variants

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/variants
- **Blocked by:** 20, 22
- **Goal:** The three Variants of ADR 0007 produce the same `TestDesign` type through the same deterministic code.
- **Scope:** Single Prompt (one call returns Requirements, Test Conditions and risk scores), Pipeline (Analyst, Designer, Prioritizer) and Pipeline with Critic. A `--variant` option on `design`.
- **Out of scope:** Raw Single Prompt, running the matrix.
- **Acceptance criteria:**
  - [ ] Single Prompt makes exactly one model call per Story when the first response is valid.
  - [ ] Pipeline never calls the Critic.
  - [ ] Given the same Test Conditions, all Variants produce identical Test Cases.
- **Tests first:** Call counts per Variant. Equal expansion for equal conditions.

### 24: OpenAI-compatible client

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/openai-compatible-client
- **Blocked by:** 12a
- **Goal:** One adapter for the free cloud tier chosen later (ADR 0001).
- **Scope:** `OpenAICompatibleClient` over `post_json`, configured by a cloud Provider Profile (base URL, model, key variable name). One example profile for a provider that offers a free tier. The API key is read from an environment variable and never printed or logged. Token counts from the response.
- **Out of scope:** Choosing the provider and the model (M5), real network calls in tests.
- **Acceptance criteria:**
  - [ ] The payload and the authorization header are correct.
  - [ ] A missing key raises an error that does not contain any key value.
  - [ ] HTTP errors and timeouts are typed.
- **Tests first:** All three, with the transport stubbed.

### 25: AnthropicClient (untested)

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/anthropic-client
- **Blocked by:** 12a
- **Goal:** `LLMClient` implemented for the Messages API, and marked untested in code and docs until the live smoke test has been run with a key (ADR 0001).
- **Scope:** `AnthropicClient` over `post_json`, with no SDK and no new dependency, configured by a cloud Provider Profile. The request format and the structured-output mechanism are taken from the official Anthropic API documentation, and the PR description links the pages used. One opt-in smoke test with the pytest marker `live`: it makes one real call, is excluded by default through the pytest options, and is never run in CI. A docstring and a README line that say the class has not been run against the real API.
- **Out of scope:** Any real call outside the `live` test, using the class in the eval.
- **Acceptance criteria:**
  - [ ] The payload shape is checked against a stubbed transport and matches the documented format.
  - [ ] `uv run pytest` does not run the `live` test, and CI does not select it.
  - [ ] The `live` test skips with a clear message when the key variable is not set.
  - [ ] The class and the README both say untested.
- **Tests first:** Payload shape and key handling with the stubbed transport. The default test run deselects `live`.

### 26: JiraSource stub

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/jira-source-stub
- **Blocked by:** 03
- **Goal:** The `RequirementsSource` interface has a visible Jira slot that does not pretend to work.
- **Scope:** `JiraSource` satisfies `RequirementsSource` and raises `NotImplementedError` with a clear message. A README line.
- **Out of scope:** Any Jira API call.
- **Acceptance criteria:**
  - [ ] Calling it raises with the message that names the stub.
  - [ ] It satisfies the Protocol under mypy.
- **Tests first:** The raise. Protocol conformance.

### M3: Stories and Test Contexts for the remaining targets

- **Status:** todo
- **Owner:** maintainer
- **Branch:** chore/corpus-remaining
- **Blocked by:** 15
- **Goal:** The rest of the corpus, written before the Bindings so their Outcome Keys are known.
- **Scope:** A held-out Story and Test Context for `parse_transaction`. Dev Stories and Test Contexts for `rules_from_env` and `render`. One Gap-probe Story with a deliberately open threshold. Manifest entries and SUT Config for each. All written from the README and DECISIONS prose of the SUT.
- **Out of scope:** Gold Test Designs (M4).
- **Acceptance criteria:**
  - [ ] Every Story loads and the Manifest loads.
  - [ ] The corpus is two held-out Stories (FRAUD, `parse_transaction`) and the Dev Stories `rules_from_env`, `render` and Synthetic, plus one Gap-probe Story.
- **Tests first:** None.

### 27: parse_transaction Binding

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/binding-parse-transaction
- **Blocked by:** 16, M3
- **Goal:** Test Cases for `parse_transaction` run through the Validity Run and the Mutation Run.
- **Scope:** A Binding that builds the JSON body from the Nominal Input and the overrides and maps `InvalidTransaction` messages to Outcome Keys. Non-injectable constants (the currency list) are recorded as expected values in the Manifest.
- **Out of scope:** The Gold Test Design (M4).
- **Acceptance criteria:**
  - [ ] Each rejection message maps to exactly one Outcome Key.
  - [ ] An unmapped message fails loudly.
  - [ ] A body that is not JSON and a body that is not an object are covered.
- **Tests first:** One mapping test per rejection. The unmapped case. A `sut` test through the runner.

### 28: rules_from_env Binding

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/binding-rules-from-env
- **Blocked by:** 16, M3
- **Goal:** `rules_from_env` can be tested although its shape is environment in and `Rules` out, not input to Decision.
- **Scope:** A Binding where the overrides are environment variables and the actual outcome is the resulting configuration, reported through the `values` field of Expected Outcome (ADR 0004). The field already exists in the schema from ticket 07. This target needs no SUT Config, since the target is the configuration, so its Manifest entry has none.
- **Out of scope:** Changes to the Expected Outcome schema, the Gold Test Design (M4).
- **Acceptance criteria:**
  - [ ] Defaults, overrides and an empty `BLOCKED_COUNTRIES` are covered.
  - [ ] Values are compared by exact equality, including `Decimal` thresholds.
  - [ ] A malformed number is reported as an outcome and does not crash the runner.
- **Tests first:** Each acceptance case.

### 29: render Binding

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/binding-render
- **Blocked by:** 16, M3
- **Goal:** Test Cases for `render` run through the Validity Run. There is no Mutation Run, because `render` is outside `domain/`.
- **Scope:** A Binding that builds records from overrides and compares the CSV text with the expected values, using the `values` field of Expected Outcome like ticket 28.
- **Out of scope:** Mutation Run, the Gold Test Design (M4).
- **Acceptance criteria:**
  - [ ] Amount formatting and empty optional fields are covered.
  - [ ] Importing the reporter module in the runner has no side effects, as the spike confirmed.
- **Tests first:** Each acceptance case.

### 30: Synthetic target and Binding

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/synthetic-target
- **Blocked by:** 16, M1
- **Goal:** The Synthetic Story has a real target to validate against.
- **Scope:** A toy fee function that implements the M1 Story as written, in its own small uv project under `eval/toys/`. A Binding for it. Validity Run only.
- **Out of scope:** Mutation Run, the Gold Test Design (M4).
- **Acceptance criteria:**
  - [ ] The runner works with `uv run --project eval/toys/<name>`.
  - [ ] Each AC of the Synthetic Story holds on its boundaries.
- **Tests first:** One test per AC boundary, then the Binding mapping.

### M4: Gold Test Designs for the remaining Stories

- **Status:** todo
- **Owner:** maintainer
- **Branch:** chore/corpus-gold
- **Blocked by:** 27, 28, 29, 30
- **Goal:** Every non-Gap-probe Story has its oracle check and, where a Mutation Run exists, its ceiling.
- **Scope:** Gold Test Designs for `parse_transaction`, `rules_from_env`, `render` and the Synthetic Story, written from the Stories.
- **Out of scope:** Gold for Gap-probe Stories.
- **Acceptance criteria:**
  - [ ] Each Gold Test Design has zero Invalid Test Cases in `eval validity`.
  - [ ] Pre-freeze edits are noted in `docs/eval-changelog.md`.
- **Tests first:** None.

### 31: Eval metrics and aggregation

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/eval-metrics
- **Blocked by:** 18
- **Goal:** All reported numbers come from one place.
- **Scope:** Duplicate Ratio, Invalid Rate, Failure Rate, tokens and wall-clock per Story. Aggregation over repeats as mean and range. Gap-probe Stories stay out of Kill Rate aggregates. A failed Story counts as zero coverage and zero kills.
- **Out of scope:** The runner, the report.
- **Acceptance criteria:**
  - [ ] A Story whose Structured Generation fails raises Failure Rate and scores zero.
  - [ ] Mean and range are correct on a hand-computed example.
  - [ ] Gap-probe results never enter Kill Rate.
- **Tests first:** The three behaviours above with hand-made results.

### 32: Prompt tuning on Dev Stories

- **Status:** todo
- **Owner:** agent
- **Branch:** chore/prompt-tuning
- **Blocked by:** 13, 23, 28, 29, 30, 31
- **Goal:** Prompts reach a stable state using Dev Stories only.
- **Scope:** Prompts stored as versioned files in the repo. A log in `docs/prompt-tuning.md` with each version and its Dev results (Invalid Rate, AC Coverage, Failure Rate). The prompt version is part of the fixture key through the prompt text. Tuning commands refuse held-out Stories. The maintainer runs the models locally and reviews the log.
- **Out of scope:** Held-out Stories, changing schemas.
- **Acceptance criteria:**
  - [ ] The loader selects a prompt by name and version.
  - [ ] Changing a prompt changes the fixture key, and CI fails until the fixtures are re-recorded.
  - [ ] No held-out Story appears in the log.
- **Tests first:** Version selection. Key change on prompt change. The held-out guard.

### 33: Spike: wall-clock of one Dev run on the ~30B model

- **Status:** todo
- **Owner:** agent
- **Branch:** chore/spike-30b-wallclock
- **Blocked by:** 11, 12a, 23
- **Goal:** Fix the size of the matrix from a measurement (ADR 0007).
- **Scope:** Run Pipeline with Critic on one Dev Story with the ~30B Provider Profile and measure wall-clock, tokens and memory. Work out the time for the planned matrix and choose the number of Stories, repeats and models. Write it to `docs/spikes/30b-wallclock.md` and update ADR 0007 if the matrix changes.
- **Out of scope:** The runner.
- **Acceptance criteria:**
  - [ ] The note has measured numbers and the chosen matrix size with the arithmetic.
- **Tests first:** None.

### 34: Eval matrix runner

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/eval-matrix
- **Blocked by:** 23, 31, 33
- **Goal:** `eval run` executes Variants, models, Stories and repeats and stores every result.
- **Scope:** Cells of Variant, Provider Profile, Story and seed. Repeats use temperature 0.3 with distinct seeds. One JSONL line per cell with metrics and mutation results. Finished cells are skipped on a rerun. Cloud cells run once and are marked. Mutation Run only for Stories with a target under `domain/`, Validity Run only for the others, none for Gap-probe Stories.
- **Out of scope:** The report, the real runs.
- **Acceptance criteria:**
  - [ ] The number of cells equals the product of the matrix dimensions.
  - [ ] A rerun skips completed cells.
  - [ ] A failed cell is recorded as a failure and is not dropped.
  - [ ] Cloud cells are marked as a single repeat.
- **Tests first:** Cell count. Resume. Failure record. Cloud marker. All with FakeLLMClient.

### 35: Eval report

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/eval-report
- **Blocked by:** 34
- **Goal:** Results as Markdown tables.
- **Scope:** Tables per Story, Variant and model with Kill Rate, the Gold ceiling, the Baseline Suite value, AC Coverage, Duplicate Ratio, Invalid Rate, Failure Rate, timeouts, tokens and time. Mean and range over repeats. Counts of excluded Equivalent and Unreachable Mutants. A header with model tags and prompt versions. Gap-probe Stories in a separate table. No charts.
- **Out of scope:** Charts (ticket 38).
- **Acceptance criteria:**
  - [ ] Kill Rate always appears with AC Coverage.
  - [ ] Gap-probe Stories do not appear in the Kill Rate tables.
  - [ ] The output is deterministic for the same results file.
- **Tests first:** A golden report from fixture results. The Kill Rate and AC Coverage pairing. The Gap-probe split.

### M5: Eval Freeze

- **Status:** todo
- **Owner:** maintainer
- **Branch:** chore/eval-freeze-v1
- **Blocked by:** 18, M4, 32, 33
- **Goal:** Everything the eval depends on is fixed before any held-out run (ADRs 0006 and 0007).
- **Scope:** Review the candidates for Equivalent Mutants and list the Unreachable Mutants. Choose the cloud provider and set the final Provider Profiles with their model tags. Freeze the prompt versions. Check that the Manifest pins the SUT commit SHA. Complete the pre-freeze changelog. After the merge, tag `eval-freeze-v1`.
- **Out of scope:** Any held-out run.
- **Acceptance criteria:**
  - [ ] The two mutant lists, the Provider Profiles, the prompt versions and the SUT SHA are committed.
  - [ ] The tag exists on the merge commit.
- **Tests first:** None.

### 36: Held-out eval runs

- **Status:** todo
- **Owner:** agent
- **Branch:** chore/eval-results
- **Blocked by:** 24, 35, M5
- **Goal:** The numbers that the README reports.
- **Scope:** A guard that refuses held-out runs unless the tag exists and `eval/` is unchanged since it. The runs themselves: the three local Provider Profiles on all Variants, and the cloud profile once. The maintainer starts them locally. Results and the generated report are committed.
- **Out of scope:** Changing any frozen input.
- **Acceptance criteria:**
  - [ ] The guard fails without the tag and on a modified corpus.
  - [ ] The results file and the report are in the PR.
- **Tests first:** The guard in both failing cases and the passing case.

### 37: README with results and Limitations

- **Status:** todo
- **Owner:** agent
- **Branch:** chore/readme-results
- **Blocked by:** 36
- **Goal:** The README reports what was measured and what was not.
- **Scope:** Result tables from the report. Limitations: a very small corpus with no significance claim, Dev prompts tuned partly on a Synthetic Story, State Transition and the other deferred items, `JiraSource` as a stub, `AnthropicClient` untested, replay CI checks wiring and not model quality, cloud results from one repeat.
- **Out of scope:** New measurements.
- **Acceptance criteria:**
  - [ ] Every number matches the committed results.
  - [ ] Each limitation named above is present.
- **Tests first:** None.

### 38: Optional: one chart

- **Status:** todo
- **Owner:** agent
- **Branch:** feat/eval-chart
- **Blocked by:** 37
- **Goal:** One chart, only if the results justify it.
- **Scope:** Kill Rate by Variant and model size as one chart from the results file. matplotlib as an eval-only dependency, which needs discussion first.
- **Out of scope:** More charts.
- **Acceptance criteria:**
  - [ ] The dependency was approved before the branch.
  - [ ] The chart is generated from the results file by one command.
- **Tests first:** The data preparation for the chart.

### 39: Optional: corpus expansion

- **Status:** todo
- **Owner:** maintainer
- **Branch:** chore/corpus-expansion
- **Blocked by:** 37
- **Goal:** More Stories for a better-supported comparison.
- **Scope:** New Stories, Test Contexts, Bindings and Gold Test Designs. This needs a new freeze tag, `eval-freeze-v2`. Results for the added Stories are reported separately from v1.
- **Out of scope:** Any edit to the v1 corpus.
- **Acceptance criteria:**
  - [ ] The v1 results are unchanged.
  - [ ] The new results sit next to them under the new tag.
- **Tests first:** None.
