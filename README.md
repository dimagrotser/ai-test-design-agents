# ai-test-design-agents

Multi-agent system that turns user stories into a typed test design: requirements, test cases built with formal techniques, risk-based priorities and traceability. An eval measures the design by running it against mutants of a real codebase. The repository currently holds only the project scaffold. Vocabulary is in `CONTEXT.md`, decisions are in `docs/adr/`, tickets are in `docs/PLAN.md`.

Requirements come from Story files through `FileSource`. `JiraSource` is an interface stub: it raises `NotImplementedError` and makes no Jira calls.
