from importlib.resources import files

from atda.adapters.anthropic import AnthropicClient, Transport
from atda.adapters.http import post_json
from atda.ports.llm import LLMClient
from atda.schemas.provider_profile import ProviderProfile, ProviderProfileError, parse_profile

# The closed set of adapters, each with the structured-output mechanisms it implements.
# It lives here because the schema is core and must not know the adapters.
MECHANISMS: dict[str, frozenset[str]] = {"anthropic": frozenset({"output_config"})}


class UnknownProfile(LookupError):
    pass


def available_profiles() -> list[str]:
    directory = files("atda.data.profiles")
    return sorted(
        p.name.removesuffix(".yaml") for p in directory.iterdir() if p.name.endswith(".yaml")
    )


def load_profile(name: str) -> ProviderProfile:
    available = available_profiles()
    # Only listed names are read, so a name never becomes a path.
    if name not in available:
        raise UnknownProfile(f"unknown profile {name!r}; available: {', '.join(available)}")
    source = files("atda.data.profiles").joinpath(f"{name}.yaml").read_text(encoding="utf-8")
    return profile_from_text(source, f"{name}.yaml")


def profile_from_text(source: str, name: str) -> ProviderProfile:
    profile = parse_profile(source, name)
    if profile.adapter not in MECHANISMS:
        known = ", ".join(sorted(MECHANISMS))
        raise ProviderProfileError(f"{name}: adapter: unknown adapter, known: {known}")
    if profile.structured_output not in MECHANISMS[profile.adapter]:
        known = ", ".join(sorted(MECHANISMS[profile.adapter]))
        raise ProviderProfileError(
            f"{name}: structured_output: the {profile.adapter} adapter defines: {known}"
        )
    return profile


def build_client(profile: ProviderProfile, *, transport: Transport | None = None) -> LLMClient:
    # profile_from_text has checked the adapter, so anthropic is the only case so far.
    assert profile.key_variable is not None
    return AnthropicClient(
        profile.model,
        endpoint=profile.endpoint,
        key_variable=profile.key_variable,
        timeout=profile.timeout,
        transport=transport or post_json,
    )
