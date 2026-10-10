# Test design FRAUD-1: Reject risky transactions

## Requirements

| Id | AC | Requirement | Priority |
| --- | --- | --- | --- |
| FRAUD-1.R1 | AC-1 | An amount over 10000 is rejected. | P1 |
| FRAUD-1.R2 | AC-2 | Transactions from KP, IR or SY are rejected. | P2 |
| FRAUD-1.R3 | AC-3 | Every broken rule is reported. | - |
| FRAUD-1.R4 | AC-4 | Five or more transactions are rejected. | P3 |

## Gaps

- AC-1: Is 10000 itself rejected?
- Story: Which currency is the limit in?

## Test cases

| Id | Technique | Input | Expected | Priority | Requirements | ACs | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-1 | BVA | amount=10000.01 | rejected (amount_limit) | P1 | FRAUD-1.R1 | AC-1 | boundary 10000 of amount (>): just above |
| TC-2 | EP | country=KP | rejected (blocked_country) | P2 | FRAUD-1.R2, FRAUD-1.R3 | AC-2, AC-3 | class 'blocked' of country: KP; decision table row 3: amount false, country true |
| TC-3 | DECISION_TABLE | amount=10000.01, country=KP | rejected (amount_limit, blocked_country) | - | FRAUD-1.R3 | AC-3 | decision table row 4: amount true, country true |
| TC-4 | BVA | Nominal input | approved {"checked": true} | P1 | FRAUD-1.R1 | AC-1 | boundary 10000 of amount (>): just below |

## Traceability

| AC | Requirement | Test cases |
| --- | --- | --- |
| AC-1: An amount over 10 000 is rejected. | FRAUD-1.R1 | TC-1, TC-4 |
| AC-2: Transactions from KP, IR or SY are rejected. | FRAUD-1.R2 | TC-2 |
| AC-3: A rejection lists every broken rule. | FRAUD-1.R3 | TC-2, TC-3 |
| AC-4: Five or more transactions are rejected. | FRAUD-1.R4 | uncovered |
| AC-5: Nothing else changes. | no requirement | uncovered |

## Checks

- Duplicate ratio before merging: 0.25
- Contradictions: TC-1, TC-4
