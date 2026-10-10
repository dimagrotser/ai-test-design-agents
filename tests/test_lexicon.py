import pytest

from atda.lexicon import Lexicon, LexiconError, implied_operators, load_lexicon, parse_lexicon
from atda.schemas.test_condition import Operator


def test_the_shipped_lexicon_covers_every_operator_with_phrases() -> None:
    lexicon = load_lexicon()

    assert set(lexicon) == set(Operator)
    assert all(phrases for phrases in lexicon.values())


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("over 10 000", {Operator.GT}),
        ("Over 10 000", {Operator.GT}),
        ("an amount ABOVE the limit", {Operator.GT}),
        ("exceeds 5", {Operator.GT}),
        ("more than 5", {Operator.GT}),
        ("at least 5", {Operator.GE}),
        ("5 or more", {Operator.GE}),
        ("no less than 5", {Operator.GE}),
        ("under 5", {Operator.LT}),
        ("fewer than 3", {Operator.LT}),
        ("at most 5", {Operator.LE}),
        ("up to 100", {Operator.LE}),
        ("no more than 5", {Operator.LE}),
        ("exactly 5", {Operator.EQ}),
        ("at least 5 but no more than 9", {Operator.GE, Operator.LE}),
        ("at  least   5", {Operator.GE}),
        ("overdraft limit", set()),
        ("the amount is 5", set()),
        ("", set()),
    ],
)
def test_the_phrases_of_a_text_imply_the_operators_they_stand_for(
    text: str, expected: set[Operator]
) -> None:
    assert implied_operators(text, load_lexicon()) == expected


def test_a_phrase_added_to_the_data_changes_the_result_without_a_code_change() -> None:
    custom: Lexicon = {Operator.GT: ("north of",), Operator.LT: ("south of",)}

    assert implied_operators("north of 5", custom) == {Operator.GT}
    assert implied_operators("south of 5", custom) == {Operator.LT}
    assert implied_operators("over 5", custom) == set()


def test_a_lexicon_file_is_parsed_into_operators_and_phrases() -> None:
    lexicon = parse_lexicon('">": [over, exceeds]\n"<=": [at most]\n', "lexicon.yaml")

    assert lexicon == {Operator.GT: ("over", "exceeds"), Operator.LE: ("at most",)}


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        ('"!=": [differs]\n', "unknown operator '!='"),
        ('">": []\n', "needs at least one phrase"),
        ('">": over\n', "must be a list"),
        ('">": [over]\n"<": [over]\n', "'over' is listed for both"),
        ('">": [""]\n', "empty phrase"),
        ("- a\n- list\n", "must be a mapping"),
        (">: [unclosed\n", "not valid YAML"),
    ],
)
def test_a_malformed_lexicon_names_the_file_and_the_problem(source: str, problem: str) -> None:
    with pytest.raises(LexiconError) as error:
        parse_lexicon(source, "operator_lexicon.yaml")

    assert str(error.value).startswith("operator_lexicon.yaml: ")
    assert problem in str(error.value)
