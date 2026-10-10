import pytest

from atda.schemas.provider_profile import ProviderProfile, ProviderProfileError, parse_profile

CLOUD = """\
adapter: anthropic
endpoint: https://api.example.test/v1/messages
model: model-x
structured_output: output_config
context_size: 200000
timeout: 120
location: cloud
key_variable: EXAMPLE_API_KEY
"""

LOCAL = """\
adapter: ollama
endpoint: http://127.0.0.1:11434/api/chat
model: model-y
structured_output: format
context_size: 16384
timeout: 600
location: local
key_variable: null
"""

FIELDS = [line.split(":")[0] for line in CLOUD.splitlines()]


def without(source: str, field: str) -> str:
    return "\n".join(line for line in source.splitlines() if not line.startswith(field + ":"))


def replacing(source: str, field: str, value: str) -> str:
    replaced = [
        f"{field}: {value}" if line.startswith(field + ":") else line
        for line in source.splitlines()
    ]
    return "\n".join(replaced)


def test_a_cloud_profile_keeps_every_field() -> None:
    profile = parse_profile(CLOUD, "cloud.yaml")

    assert profile == ProviderProfile(
        adapter="anthropic",
        endpoint="https://api.example.test/v1/messages",
        model="model-x",
        structured_output="output_config",
        context_size=200000,
        timeout=120.0,
        location="cloud",
        key_variable="EXAMPLE_API_KEY",
    )


def test_a_local_profile_has_no_key_variable() -> None:
    profile = parse_profile(LOCAL, "local.yaml")

    assert profile.location == "local"
    assert profile.key_variable is None


@pytest.mark.parametrize("field", FIELDS)
def test_a_missing_field_is_rejected_and_named(field: str) -> None:
    with pytest.raises(ProviderProfileError, match=field):
        parse_profile(without(CLOUD, field), "cloud.yaml")


def test_an_unknown_field_is_rejected() -> None:
    with pytest.raises(ProviderProfileError, match="api_key"):
        parse_profile(CLOUD + "api_key: abc\n", "cloud.yaml")


def test_a_cloud_profile_without_a_key_variable_is_rejected() -> None:
    with pytest.raises(ProviderProfileError, match="cloud profile needs a key_variable"):
        parse_profile(replacing(CLOUD, "key_variable", "null"), "cloud.yaml")


def test_a_local_profile_with_a_key_variable_is_rejected() -> None:
    with pytest.raises(ProviderProfileError, match="local profile must not have a key_variable"):
        parse_profile(replacing(LOCAL, "key_variable", "SOME_KEY"), "local.yaml")


@pytest.mark.parametrize(
    "pasted",
    ["sk-ant-api03-abc123", "sk_live_abc", "abc123", "key with space", "lower_case"],
)
def test_a_key_value_in_place_of_a_variable_name_is_rejected_without_repeating_it(
    pasted: str,
) -> None:
    source = replacing(CLOUD, "key_variable", f'"{pasted}"')

    with pytest.raises(ProviderProfileError) as error:
        parse_profile(source, "cloud.yaml")

    assert "key_variable" in str(error.value)
    assert pasted not in str(error.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("endpoint", "ftp://example.test"),
        ("endpoint", "not a url"),
        ("timeout", "0"),
        ("context_size", "0"),
        ("location", "moon"),
        ("model", '""'),
    ],
)
def test_an_invalid_value_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ProviderProfileError, match=field):
        parse_profile(replacing(CLOUD, field, value), "cloud.yaml")


def test_errors_start_with_the_source_name() -> None:
    with pytest.raises(ProviderProfileError) as error:
        parse_profile("adapter: [", "broken.yaml")

    assert str(error.value).startswith("broken.yaml: ")


def test_a_non_mapping_is_rejected() -> None:
    with pytest.raises(ProviderProfileError, match="mapping"):
        parse_profile("- a\n- b\n", "list.yaml")
