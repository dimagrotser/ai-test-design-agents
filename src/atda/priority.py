from atda.schemas.risk import Priority, Risk
from atda.schemas.test_design import TestDesign

# Written out cell by cell on purpose, so each pair can be read and tested on its own.
PRIORITY_TABLE: dict[tuple[int, int], Priority] = {
    (1, 1): Priority.P3,
    (1, 2): Priority.P3,
    (1, 3): Priority.P2,
    (2, 1): Priority.P3,
    (2, 2): Priority.P2,
    (2, 3): Priority.P1,
    (3, 1): Priority.P2,
    (3, 2): Priority.P1,
    (3, 3): Priority.P1,
}
HIGHEST_FIRST = (Priority.P1, Priority.P2, Priority.P3)


def priority_of(risk: Risk) -> Priority:
    return PRIORITY_TABLE[(risk.likelihood, risk.impact)]


def with_priorities(design: TestDesign) -> TestDesign:
    rated = {r.id: priority_of(r.risk) for r in design.requirements if r.risk is not None}
    cases = []
    for case in design.test_cases:
        found = [rated[i] for i in case.requirement_ids if i in rated]
        priority = min(found, key=HIGHEST_FIRST.index) if found else None
        cases.append(case.model_copy(update={"priority": priority}))
    return design.model_copy(update={"test_cases": tuple(cases)})
