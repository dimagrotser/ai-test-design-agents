import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from atda.schemas.outcome import ExpectedOutcome
from atda.schemas.scalar import Scalar
from atda.schemas.test_design import Contradiction, TestCase

# A text counts as a number when it looks like one and has no leading zero, so "007" stays text.
NUMBER_TEXT = re.compile(r"-?(0|[1-9]\d*)(\.\d+)?")


InputKey = tuple[tuple[str, tuple[str, str]], ...]


@dataclass(frozen=True)
class MergeResult:
    cases: tuple[TestCase, ...]
    duplicate_ratio: float
    contradictions: tuple[Contradiction, ...]


def merge_duplicates(cases: Sequence[TestCase], nominal_input: Mapping[str, Scalar]) -> MergeResult:
    groups: dict[InputKey, list[tuple[int, TestCase]]] = {}
    for index, case in enumerate(cases):
        groups.setdefault(input_key(nominal_input, case.overrides), []).append((index, case))
    ratio = 1 - len(groups) / len(cases) if cases else 0.0

    survivors: list[tuple[int, TestCase]] = []
    contradictions: list[Contradiction] = []
    for group in groups.values():
        by_outcome: dict[str, list[tuple[int, TestCase]]] = {}
        for index, case in group:
            by_outcome.setdefault(outcome_key(case.expected), []).append((index, case))
        kept = [(same[0][0], _merge([case for _, case in same])) for same in by_outcome.values()]
        if len(kept) > 1:
            contradictions.append(Contradiction(case_ids=tuple(case.id for _, case in kept)))
        survivors += kept
    survivors.sort(key=lambda pair: pair[0])
    return MergeResult(
        cases=tuple(case for _, case in survivors),
        duplicate_ratio=ratio,
        contradictions=tuple(contradictions),
    )


def _merge(same: list[TestCase]) -> TestCase:
    first = same[0]
    if len(same) == 1:
        return first
    return first.model_copy(
        update={
            "requirement_ids": tuple(dict.fromkeys(i for c in same for i in c.requirement_ids)),
            "ac_ids": tuple(dict.fromkeys(i for c in same for i in c.ac_ids)),
            "rationale": "; ".join(dict.fromkeys(c.rationale for c in same)),
        }
    )


def outcome_key(outcome: ExpectedOutcome) -> str:
    return json.dumps(outcome.model_dump(mode="json"), sort_keys=True)


def input_key(nominal_input: Mapping[str, Scalar], overrides: Mapping[str, Scalar]) -> InputKey:
    full = {**nominal_input, **overrides}
    return tuple(sorted((name, _normalize(value)) for name, value in full.items()))


def _normalize(value: Scalar) -> tuple[str, str]:
    if isinstance(value, bool):
        return "boolean", str(value)
    if isinstance(value, int | float) or NUMBER_TEXT.fullmatch(value):
        return "number", format(Decimal(str(value)).normalize(), "f")
    return "text", value
