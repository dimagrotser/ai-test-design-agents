# ai-test-design-agents

Multi-agent system that turns user stories into a typed test design: requirements, test cases built with formal techniques, risk-based priorities and traceability. A separate eval measures the quality of that design by running it against mutants of a real codebase.

## Language

### Requirements

**Story**:
A requirements document written by a human, with an id, a title, free text and a list of Acceptance Criteria. It is the input of the pipeline.
_Avoid_: Ticket, issue, user story (as a type name)

**Acceptance Criterion** (AC):
A single checkable statement inside a Story, with an id such as `AC-3`. ACs are written by humans and are the ground truth for coverage.
_Avoid_: Requirement, rule

**Requirement**:
An atomic, testable statement extracted by the Requirements Analyst from one AC, with a stable id such as `FRAUD-1.R3`. One AC can yield several Requirements.
_Avoid_: AC, spec

**Gap**:
An ambiguity or omission in a Story found by the Requirements Analyst, for example an inclusive-or-exclusive boundary that the text does not settle. A Gap is reported and never blocks the pipeline.
_Avoid_: Issue, question, defect

### Test design

**Technique**:
A formal test design method. v1 supports Equivalence Partitioning (EP), Boundary Value Analysis (BVA) and Decision Table.
_Avoid_: Strategy, approach

**Test Condition**:
A structured fact extracted by the Test Designer from a Requirement: an input, its classes or boundaries, the comparison operator, and the Expected Outcome on each side. It carries a verbatim quote from the AC as evidence.
_Avoid_: Scenario, case

**Test Case**:
A concrete input override with an Expected Outcome, produced by deterministic code from a Test Condition. It records its Technique and the rationale for it, and traces to one or more Requirements and ACs (several after duplicates are merged).
_Avoid_: Test, scenario

**Nominal Input**:
One valid, unremarkable input for a target, defined by the Test Context. A Test Case is expressed as overrides of individual fields of the Nominal Input.
_Avoid_: Default input, happy path

**Expected Outcome**:
The result a Test Case predicts, written in the vocabulary of the Story as a status plus a set of Outcome Keys. It never refers to code-level names.
_Avoid_: Oracle value, assertion

**Outcome Key**:
A name for one business rule that can decide an outcome, such as `amount_limit`. The set of keys for a Story is declared in its Test Context.
_Avoid_: Rule, reason code

**Test Context**:
The data an executor needs and a real Story does not contain: the target, the Nominal Input and the Outcome Keys. It is mandatory in v1 and lives in the Corpus Manifest.
_Avoid_: Fixture, metadata

**Priority**:
A level (P1 to P3) computed by code from a likelihood and an impact score that the Risk Prioritizer assigns to a Requirement. Each Test Case inherits the Priority of its Requirement.
_Avoid_: Severity, risk level

**Test Design**:
The typed output of the pipeline: Requirements, Gaps, Test Cases with Priorities, and the trace from AC to Requirement to Test Case. It is the object that is evaluated.
_Avoid_: Test plan, test suite

### Review

**Finding**:
A typed problem reported against a Requirement or Test Case, with a severity. Code produces coverage, traceability and duplicate Findings, and the Critic produces semantic ones.
_Avoid_: Comment, issue

**Contradiction**:
Two Test Cases with the same normalized input and different Expected Outcomes. It is always a blocking Finding.
_Avoid_: Conflict

**Refinement Loop**:
The bounded cycle in which blocking Findings go back to the Test Designer for another attempt. It runs at most two iterations.
_Avoid_: Feedback loop, retry

### Pipeline

**Requirements Analyst**, **Test Designer**, **Risk Prioritizer**, **Critic**, **Code Generator**:
The five agents, in pipeline order. Each takes and returns a Pydantic model.
_Avoid_: Worker, step

**Variant**:
One way to produce a Test Design that the eval compares: Single Prompt (one LLM call, then the same deterministic code), Pipeline (Requirements Analyst, Test Designer, Risk Prioritizer), and Pipeline with Critic. The Code Generator is outside the Variants.
_Avoid_: Mode, configuration

**Structured Generation**:
One LLM call whose output is validated against a Pydantic schema and retried with the validation error text, up to a bounded number of attempts. If all attempts fail, the raised exception carries the attempt history; this is separate from the Refinement Loop, which reruns a successful stage.
_Avoid_: Parsing, output fixing

### Evaluation

**System Under Test** (SUT):
The codebase whose behavior the Test Designs describe, here the `event-driven-payments` repository. It is never imported into this project.
_Avoid_: Target app, subject

**Corpus Manifest**:
A file that maps each eval Story to its Test Context, SUT Config, split and class. Agents see only the Test Context taken from it, never the split, class or SUT Config.
_Avoid_: Config, index

**Dev Story**, **Held-out Story**:
Dev Stories are used to tune prompts and to record Replay Fixtures. Held-out Stories are used only for reported numbers.
_Avoid_: Train, test set

**Gap-probe Story**:
A Story that is deliberately ambiguous, for example with no threshold stated. It is excluded from Kill Rate aggregates.
_Avoid_: Negative story

**Synthetic Story**:
A Story about a toy function outside the SUT, used for tuning when no real target has the needed boundaries. It gets a Validity Run only, with no Mutation Run.
_Avoid_: Mock story

**Eval Freeze**:
The git tag `eval-freeze-v1`, placed after the last edit of Stories, Manifest, Gold Test Designs, Bindings and the equivalent-mutant list. Nothing in the eval corpus changes after it.
_Avoid_: Snapshot, release

**Gold Test Design**:
A Test Design written by hand from a Story, before any model run. It validates the oracle and gives the Kill Rate ceiling for that Story.
_Avoid_: Reference, golden file

**Binding**:
Hand-written code that builds the SUT input from a Test Case and maps the SUT result back to an Expected Outcome. It is trusted infrastructure and has its own unit tests.
_Avoid_: Adapter, mapper

**SUT Config**:
The thresholds and lists the Binding injects into the SUT for a Story, such as the maximum amount, so that the Story and the SUT cannot diverge. It comes from the Corpus Manifest and is hidden from agents.
_Avoid_: Settings, rules

**Validity Run**:
Executing Test Cases against the unmodified SUT through the Binding. Test Cases that fail here are Invalid Test Cases.
_Avoid_: Smoke run

**Invalid Test Case**:
A Test Case whose Expected Outcome does not match the unmodified SUT. It does not count toward Kill Rate, and the share of such cases is published as the Invalid Rate.
_Avoid_: Failing test, broken test

**Mutation Run**:
Executing the valid Test Cases against each mutant of the SUT target code, generated by mutmut. A mutant is killed when at least one Test Case fails on it.
_Avoid_: Fuzzing

**Equivalent Mutant**:
A mutant that cannot change observable behavior. They are identified once by hand before Eval Freeze and removed from the denominator for every Variant.
_Avoid_: Ignored mutant

**Kill Rate**:
The share of non-equivalent mutants killed by a Test Design, also known as mutation score. It is always reported next to AC Coverage, the Gold Test Design value and the Baseline Suite value.

**Baseline Suite**:
The 33 existing unit tests of the SUT, run through the same Mutation Run. It is the reference for human-written tests.
_Avoid_: Existing tests

**AC Coverage**:
The share of ACs that have at least one Test Case through a Requirement, and the only coverage metric that is reported. Requirement coverage is an internal Critic check, and AC Coverage is never reported without Kill Rate.
_Avoid_: Requirement coverage

**Duplicate Ratio**:
One minus unique over total Test Cases, where uniqueness is the target plus the normalized input, measured before duplicates are merged. Part of it comes from deterministic expansion, for example the all-false row of a Decision Table repeating a boundary case, and does not reflect model quality.
_Avoid_: Redundancy

**Failure Rate**:
The share of Stories for which Structured Generation ran out of attempts and produced no Test Design. Such a Story scores zero coverage and zero kills.
_Avoid_: Error rate

**Replay Fixture**:
A recorded LLM response keyed by a hash of model, messages, schema, temperature, seed and context size. Replay-based CI checks pipeline wiring, not model quality.
_Avoid_: Cassette, mock

## Deferred

- **Raw Single Prompt**: a Variant where one LLM call produces finished Test Cases without deterministic expansion.
- **State Transition**: deferred until a stateful target exists.
- **Pairwise** and **Error Guessing**: deferred until a scenario needs them.
- **Code Generator evaluation**: generated tests must pass on the original SUT and kill the same mutants.
- **Gap quality scoring**: needs a human or LLM judge to match Gaps to known gaps.
- **Story without Test Context**: arrives with GitHubIssuesSource.
- **TMS export**.

## Flagged ambiguities

- The SUT compares the amount limit without looking at currency. For `eval-freeze-v1` this is accepted behavior, and the FRAUD Story stays silent on currency so that it surfaces as a Gap.
- "Rule" meant both a business rule in a Story and a threshold passed to the SUT. These are now **Outcome Key** and **SUT Config**.
