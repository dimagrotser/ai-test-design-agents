from atda.ports.requirements import RequirementsSource
from atda.schemas.story import Story


# Interface stub only: there is no Jira access, so nothing here calls Jira.
class JiraSource(RequirementsSource):
    def load(self, ref: str) -> Story:
        raise NotImplementedError(
            f"JiraSource is an interface stub with no Jira integration; cannot load {ref}. "
            "Use FileSource."
        )
