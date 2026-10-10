# ai-test-design-agents

Turns a user Story with Acceptance Criteria into a typed Test Design: Requirements, Test Cases built with Equivalence Partitioning, Boundary Value Analysis and Decision Table, risk-based Priorities, and traceability from each Acceptance Criterion to its Requirements and Test Cases. The agents are plain Python functions between Pydantic models and the core does not depend on any model provider.

A separate eval is planned. It will measure a Test Design by running it against mutants of a real codebase (mutation testing) and will compare a single prompt with a multi-agent pipeline across models. It does not exist yet and this repository reports no eval results.

Vocabulary is in [`CONTEXT.md`](CONTEXT.md), decisions are in [`docs/adr/`](docs/adr/), tickets are in [`docs/PLAN.md`](docs/PLAN.md).

## Status

| Area | State |
| --- | --- |
| Story and Test Context loading, Corpus Manifest loader | implemented |
| Structured Generation (schema validation, bounded retry with the error text) | implemented |
| Requirements Analyst, Test Designer, Risk Prioritizer | implemented |
| Critic and Refinement Loop, deterministic Findings | implemented |
| Three Variants: `single-prompt`, `pipeline`, `pipeline-with-critic` | implemented |
| Test Design report (`test-design.json`, `test-design.md`) | implemented |
| Provider Profiles, `AnthropicClient`, `OpenAICompatibleClient` | implemented |
| `AnthropicClient` against the real API | one opt-in `live` test, run by hand |
| `OpenAICompatibleClient` against a real server | not run yet |
| `ReplayClient`, `RecordingClient`, `record` command | implemented, no fixtures recorded yet |
| `JiraSource` | stub: raises `NotImplementedError`, makes no Jira calls |
| Ollama client | planned |
| Bindings, Validity Run, Mutation Run, Kill Rate | planned |
| Eval matrix and report | planned |
| `GitHubIssuesSource`, automated test code generation | planned |

## Architecture

- **Ports and adapters.** The core depends on two `typing.Protocol` ports, `LLMClient` and `RequirementsSource`. Adapters in `src/atda/adapters/` implement them: `AnthropicClient`, `OpenAICompatibleClient`, `ReplayClient`, `FakeLLMClient`, `FileSource`, `JiraSource`. The command line is an adapter too.
- **Import rule.** Nothing outside `adapters/` imports from it. `tests/test_import_rule.py` fails if it does.
- **Agents are functions.** The Requirements Analyst, Test Designer, Risk Prioritizer and Critic each turn one Pydantic model into another. There is no agent framework. Pipeline with Critic wraps the Designer in a Refinement Loop of at most two rounds.
- **Structured Generation.** Model output is validated against a Pydantic model. On failure the error text is appended to the prompt and the call is repeated, up to a bounded number of attempts. The attempt history is kept in the raised exception.
- **The model extracts, code expands.** The model returns Test Conditions: boundaries, equivalence classes, decision table inputs. Deterministic code expands them into Test Cases, merges duplicates, checks evidence against the Acceptance Criterion text and assigns Priorities from a fixed 3 by 3 table (ADR 0002).
- **Oracle in Story vocabulary.** Expected results are a status plus Outcome Keys named in a Test Context file next to the Story, never code-level names (ADR 0004, ADR 0008).

## Install and check

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```
uv sync
uv run pytest
uv run ruff check .
uv run mypy src
```

## Usage

Run the pipeline on the Synthetic Story in `eval/corpus/stories/`. A model profile needs its key in an environment variable. Keys are never read from files in the repository.

```
export ANTHROPIC_API_KEY=...
uv run atda design eval/corpus/stories/fee.md \
  --context eval/corpus/stories/fee.context.yaml \
  --profile claude-sonnet-5-5 \
  --out out/fee
```

This writes `out/fee/test-design.json` and `out/fee/test-design.md`. Without `--out` the Story, the Test Context and the Test Design are printed as JSON.

- `--variant single-prompt|pipeline|pipeline-with-critic` selects how the design is produced. The default is `pipeline`.
- `--profile` takes the name of a file in `src/atda/data/profiles/`: `claude-sonnet-5-5` and the example `groq-gpt-oss-120b`. A profile holds the adapter, endpoint, model tag, structured-output mechanism, context size, timeout and the name of the key variable.
- `--fake-responses FILE` replaces the model with a JSON list of scripted answers. This is how the tests run.

## Replay

`record` runs the pipeline on a Story from the Corpus Manifest at temperature 0 and saves every model answer as a fixture. It refuses held-out Stories.

```
uv run atda record FEE-1 --profile claude-sonnet-5-5 --out recorded/FEE-1
uv run atda design eval/corpus/stories/fee.md \
  --context eval/corpus/stories/fee.context.yaml \
  --profile claude-sonnet-5-5 --replay recorded/FEE-1/fixtures
```

A fixture is keyed by a hash of the model, messages, schema, temperature, seed and context size, and holds only the request body and the response body, never headers or keys. A changed prompt finds no fixture and fails with the missing key instead of returning an old answer.

Replay-based CI checks pipeline wiring, not model quality. No fixtures are recorded yet and `eval/corpus/manifest.yaml` does not exist yet, so CI runs no replay step. When fixtures are committed they will have been recorded with the `claude-sonnet-5-5` profile.

## Limitations

- The corpus holds one Synthetic Story. There are no eval numbers, and a corpus this small will not support significance claims.
- A Test Context file is mandatory and written by hand. A Story from a tracker does not have one.
- Only Equivalence Partitioning, Boundary Value Analysis and Decision Table are supported.
- `OpenAICompatibleClient` has not been run against a real server. `AnthropicClient` has one manual `live` test.
- Replay Fixtures depend on a hosted model whose behavior can change.
- No Jira or GitHub integration. `JiraSource` is a stub.
- No generated test code and no mutation testing yet.
