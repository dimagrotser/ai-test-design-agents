# Claude API as the first real provider

I now have a Claude API key. ADR 0001 assumed none and planned `AnthropicClient` as implemented but untested. Claude is now the first real provider: the pipeline is developed against it and the Replay Fixtures are recorded with it. `AnthropicClient` gets an opt-in `live` smoke test that I run by hand, and CI never runs it. `post_json` moves into the `AnthropicClient` ticket.

Ollama and the local models stay the basis of the eval matrix, because the matrix compares model sizes and Claude does not offer three sizes of one family. Ollama setup and `OllamaClient` move to ship point 3. The cloud provider of the eval is still chosen at Eval Freeze.

## Consequences

Development and recording cost money and need a key in an environment variable. Fixtures come from a hosted model whose behavior can change, so the fixture key includes the model tag. The ports, the import rule and Provider Profiles do not change. The README must say that the Replay Fixtures were recorded with Claude and that the eval compares local models.
