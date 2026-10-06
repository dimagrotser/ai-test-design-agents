from typing import Protocol

from atda.schemas.story import Story


class RequirementsSource(Protocol):
    def load(self, ref: str) -> Story: ...
