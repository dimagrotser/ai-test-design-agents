---
id: FEE-1
title: Transaction fee
---
A payment is charged a fee that depends on its amount and on the card. Amounts are positive decimals in EUR with two decimal places.

## Acceptance criteria

- AC-1: An amount of at most 100.00 is charged the flat fee of 1.00.
- AC-2: An amount over 100.00 is charged a fee of 1.5 percent of the amount.
- AC-3: A card type other than credit or debit is rejected as unsupported.
- AC-4: An international payment by credit card is charged the cross-border surcharge of 2.00 in addition to its fee. A domestic payment, or a debit card payment, is not.
