import re
from collections.abc import Mapping
from functools import cache
from importlib.resources import files

import yaml

from atda.schemas.strict_yaml import load_yaml
from atda.schemas.test_condition import Operator

Lexicon = Mapping[Operator, tuple[str, ...]]


class LexiconError(ValueError):
    pass


def parse_lexicon(source: str, name: str) -> Lexicon:
    try:
        raw = load_yaml(source)
    except yaml.YAMLError as error:
        raise LexiconError(f"{name}: not valid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise LexiconError(f"{name}: the top level must be a mapping")
    lexicon: dict[Operator, tuple[str, ...]] = {}
    owner: dict[str, str] = {}
    for key, phrases in raw.items():
        try:
            operator = Operator(key)
        except ValueError:
            raise LexiconError(f"{name}: unknown operator {key!r}") from None
        if not isinstance(phrases, list):
            raise LexiconError(f"{name}: the phrases of {key} must be a list")
        if not phrases:
            raise LexiconError(f"{name}: {key} needs at least one phrase")
        for phrase in phrases:
            if not isinstance(phrase, str) or not phrase.strip():
                raise LexiconError(f"{name}: {key} has an empty phrase")
            lowered = " ".join(phrase.lower().split())
            if lowered in owner and owner[lowered] != key:
                raise LexiconError(
                    f"{name}: {phrase!r} is listed for both {owner[lowered]} and {key}"
                )
            owner[lowered] = key
        lexicon[operator] = tuple(phrases)
    return lexicon


@cache
def load_lexicon() -> Lexicon:
    path = files("atda.data").joinpath("operator_lexicon.yaml")
    return parse_lexicon(path.read_text(encoding="utf-8"), "operator_lexicon.yaml")


def implied_operators(text: str, lexicon: Lexicon) -> set[Operator]:
    """The operators that the phrases found in the text stand for.

    Longer phrases are tried first and matches do not overlap, so "no more than" counts as
    "<=" and the "more than" inside it is not read again as ">".
    """
    by_phrase = {
        " ".join(phrase.lower().split()): operator
        for operator, phrases in lexicon.items()
        for phrase in phrases
    }
    if not by_phrase:
        return set()
    alternatives = sorted(by_phrase, key=len, reverse=True)
    pattern = re.compile(
        r"\b(?:" + "|".join(r"\s+".join(map(re.escape, p.split())) for p in alternatives) + r")\b",
        re.IGNORECASE,
    )
    return {by_phrase[" ".join(match.group().lower().split())] for match in pattern.finditer(text)}
