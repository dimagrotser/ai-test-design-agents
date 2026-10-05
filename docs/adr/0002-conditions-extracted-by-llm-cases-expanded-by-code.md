# LLM extracts Test Conditions, code expands Test Cases

The Test Designer asks the model for Test Conditions: inputs, classes, boundaries, the comparison operator and the Expected Outcome on each side. Deterministic code expands them into Test Cases. For BVA it computes the points around a boundary, and for a Decision Table it builds the combinations.

I chose this over letting the model write finished Test Cases because boundary values are then correct by construction, duplicates can be measured exactly, and small models only have to extract facts instead of generating data. The main failure risk moves to the operator (`>` against `>=`). Each condition therefore carries a verbatim quote from the AC, which code checks as a substring. A phrase lexicon in the Critic warns when the operator contradicts the wording, and an ambiguous AC must produce a Gap instead of a guess.

## Consequences

Unusual negative cases that do not fit the Test Condition schema cannot be expressed. A wrong operator shows up twice in the eval: as Invalid Test Cases and as a lower Kill Rate.
