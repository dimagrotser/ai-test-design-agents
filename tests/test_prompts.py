import pytest

from atda.prompts import load_prompt


def test_a_prompt_is_loaded_by_name() -> None:
    prompt = load_prompt("retry")

    assert "{error}" in prompt
    assert prompt == prompt.strip()


def test_an_unknown_prompt_fails_with_its_name() -> None:
    with pytest.raises(FileNotFoundError, match="no prompt named 'missing'"):
        load_prompt("missing")
