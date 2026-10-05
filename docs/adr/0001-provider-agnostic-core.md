# Provider-agnostic core with ports and adapters

The core depends on two `typing.Protocol` ports, `LLMClient` and `RequirementsSource`, and never imports from `adapters/`. I have no Jira access and no Claude API access. Provider independence is also a realistic requirement, since a team with confidential fintech requirements may not be able to send them to a hosted API. Adapters implement the ports: `OllamaClient`, one OpenAI-compatible client for a free cloud tier, `ReplayClient` for CI without keys, `FakeLLMClient` for unit tests, and `FileSource` for Stories.

`JiraSource` is an interface stub only and the README says so. `AnthropicClient` is implemented against the port but has never been run against the real API, and it is marked untested in code and docs. `GitHubIssuesSource` comes later.

## Consequences

The import rule can be checked mechanically: a test fails if anything in the core imports from `adapters/`. Features that exist in only one provider, such as native JSON schema output, cannot be assumed. Structured Generation in the core covers providers that lack them.
