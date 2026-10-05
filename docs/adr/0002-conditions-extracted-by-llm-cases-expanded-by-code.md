# LLM extracts Test Conditions, code expands Test Cases

The Test Designer asks the model for Test Conditions: inputs, classes, boundaries, the comparison operator and the Expected Outcome on each side. Deterministic code expands them into Test Cases. For BVA it computes the points around a boundary, and for a Decision Table it builds the combinations.

I chose this over letting the model write finished Test Cases because boundary values are then correct by construction, duplicates can be measured exactly, and small models only have to extract facts instead of generating data. The main failure risk moves to the operator (`>` against `>=`). Each condition therefore carries a verbatim quote from the AC, which code checks as a substring. A deterministic check run alongside the Critic warns, from a phrase lexicon, when the operator contradicts the wording, and an ambiguous AC must produce a Gap instead of a guess.

## Consequences

Single Prompt uses the same deterministic expansion, so the Variant comparison isolates decomposition into agents, not the effect of code.

Unusual negative cases that do not fit the Test Condition schema cannot be expressed. A wrong operator shows up twice in the eval: as Invalid Test Cases and as a lower Kill Rate.
