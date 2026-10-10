import pytest

from atda.adapters.jira_source import JiraSource
from atda.ports.requirements import RequirementsSource


def test_loading_raises_an_error_that_names_the_stub_and_the_ref() -> None:
    with pytest.raises(NotImplementedError, match=r"JiraSource.*stub.*PAY-1"):
        JiraSource().load("PAY-1")


def test_jira_source_is_accepted_where_a_requirements_source_is_expected() -> None:
    source: RequirementsSource = JiraSource()

    with pytest.raises(NotImplementedError):
        source.load("PAY-2")
