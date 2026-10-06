import re

import yaml


class _Loader(yaml.SafeLoader):
    pass


# YAML 1.1 reads no, yes, on and off as booleans, so an unquoted country code like NO
# loads as False. Only true and false are booleans here.
_Loader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_yaml(source: str) -> object:
    loaded: object = yaml.load(source, Loader=_Loader)
    return loaded
