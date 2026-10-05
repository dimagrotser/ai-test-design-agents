# Plain Python pipeline instead of an agent framework

The agents are functions from one Pydantic model to another, called in order, with one explicit Refinement Loop for the Critic. I do not use LangGraph or a similar framework. The graph is linear with a single bounded loop, so a framework would add a dependency and typing friction under strict mypy without removing any code.

Findings from the Critic go back to the Test Designer only, never to the Requirements Analyst. Requirement ids must stay stable after extraction, because traceability and AC Coverage depend on them.

## Considered Options

An agent framework with a state graph: rejected for the reasons above. It can be reconsidered if the pipeline gains branching.
