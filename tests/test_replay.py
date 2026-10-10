import json
from pathlib import Path

import pytest

from atda.adapters.replay import (
    FixtureError,
    FixtureStore,
    MissingFixture,
    ReplayClient,
    fixture_key,
)
from atda.ports.llm import LLMClient, LLMRequest, LLMResponse, Message

MODEL = "model-x"


def request(**overrides: object) -> LLMRequest:
    fields: dict[str, object] = {
        "messages": (
            Message(role="system", content="Be exact."),
            Message(role="user", content="Story S-1\nAC-1: over 100"),
        ),
        "json_schema": {"type": "object", "properties": {"a": {"type": "integer"}}},
        "temperature": 0.0,
        "seed": 7,
        "num_ctx": 4096,
    }
    return LLMRequest.model_validate(fields | overrides)


CHANGES: dict[str, object] = {
    "messages": (Message(role="user", content="Story S-1\nAC-1: over 101"),),
    "json_schema": {"type": "object", "properties": {"b": {"type": "integer"}}},
    "temperature": 0.3,
    "seed": 8,
    "num_ctx": 8192,
}


def test_the_key_is_stable_for_equal_inputs() -> None:
    assert fixture_key(request(), MODEL) == fixture_key(request(), MODEL)


def test_the_key_is_a_sha256_hex_digest() -> None:
    key = fixture_key(request(), MODEL)

    assert len(key) == 64
    assert set(key) <= set("0123456789abcdef")


def test_changing_the_model_changes_the_key() -> None:
    assert fixture_key(request(), MODEL) != fixture_key(request(), "model-y")


@pytest.mark.parametrize("component", sorted(CHANGES))
def test_changing_any_other_component_changes_the_key(component: str) -> None:
    changed = request(**{component: CHANGES[component]})

    assert fixture_key(changed, MODEL) != fixture_key(request(), MODEL)


def test_the_six_components_give_six_different_keys() -> None:
    keys = {fixture_key(request(**{c: v}), MODEL) for c, v in CHANGES.items()}
    keys.add(fixture_key(request(), "model-y"))

    assert len(keys) == 6


def test_an_unset_seed_and_context_size_hash_as_null() -> None:
    unset = request(seed=None, num_ctx=None)

    assert fixture_key(unset, MODEL) != fixture_key(request(), MODEL)
    assert fixture_key(unset, MODEL) == fixture_key(request(seed=None, num_ctx=None), MODEL)


def test_the_order_of_schema_keys_does_not_change_the_key() -> None:
    one = request(json_schema={"a": 1, "b": 2})
    other = request(json_schema={"b": 2, "a": 1})

    assert fixture_key(one, MODEL) == fixture_key(other, MODEL)


def test_message_roles_are_part_of_the_key() -> None:
    swapped = request(
        messages=(
            Message(role="user", content="Be exact."),
            Message(role="user", content="Story S-1\nAC-1: over 100"),
        )
    )

    assert fixture_key(swapped, MODEL) != fixture_key(request(), MODEL)


def test_a_saved_fixture_reads_back_equal(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    response = LLMResponse(text='{"a": 1}', input_tokens=11, output_tokens=7)

    key = store.save(request(), MODEL, response)

    assert key == fixture_key(request(), MODEL)
    assert store.load(key) == response


def test_a_fixture_file_holds_only_the_model_the_request_and_the_response(
    tmp_path: Path,
) -> None:
    store = FixtureStore(tmp_path)

    key = store.save(request(), MODEL, LLMResponse(text="x", input_tokens=1, output_tokens=2))

    stored = json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8"))
    assert set(stored) == {"model", "request", "response"}
    assert stored["model"] == MODEL
    assert set(stored["request"]) == {"messages", "json_schema", "temperature", "seed", "num_ctx"}
    assert stored["response"] == {"text": "x", "input_tokens": 1, "output_tokens": 2}


def test_saving_the_same_call_twice_gives_identical_bytes(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    response = LLMResponse(text="x", input_tokens=1, output_tokens=2)

    key = store.save(request(), MODEL, response)
    first = (tmp_path / f"{key}.json").read_bytes()
    store.save(request(), MODEL, response)

    assert (tmp_path / f"{key}.json").read_bytes() == first
    assert first.endswith(b"\n")


def test_the_store_creates_its_directory_on_the_first_save(tmp_path: Path) -> None:
    directory = tmp_path / "a" / "fixtures"

    FixtureStore(directory).save(
        request(), MODEL, LLMResponse(text="x", input_tokens=0, output_tokens=0)
    )

    assert directory.is_dir()


def test_loading_an_unknown_key_returns_nothing(tmp_path: Path) -> None:
    assert FixtureStore(tmp_path).load("0" * 64) is None


def test_a_malformed_fixture_file_is_reported_with_its_path(tmp_path: Path) -> None:
    key = "a" * 64
    (tmp_path / f"{key}.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(FixtureError, match=key):
        FixtureStore(tmp_path).load(key)


def test_replay_returns_the_recorded_response(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    recorded = LLMResponse(text='{"a": 1}', input_tokens=11, output_tokens=7)
    store.save(request(), MODEL, recorded)

    assert ReplayClient(store, MODEL).complete(request()) == recorded


def test_replay_without_a_matching_fixture_raises_and_shows_the_key(tmp_path: Path) -> None:
    with pytest.raises(MissingFixture) as error:
        ReplayClient(FixtureStore(tmp_path), MODEL).complete(request())

    assert fixture_key(request(), MODEL) in str(error.value)
    assert MODEL in str(error.value)


def test_a_changed_prompt_fails_instead_of_returning_the_old_answer(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    store.save(request(), MODEL, LLMResponse(text="old", input_tokens=1, output_tokens=1))
    edited = request(
        messages=(
            Message(role="system", content="Be exact."),
            Message(role="user", content="Story S-1\nAC-1: over 100."),
        )
    )

    with pytest.raises(MissingFixture, match="AC-1"):
        ReplayClient(store, MODEL).complete(edited)


def test_replay_with_another_model_does_not_find_the_fixture(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    store.save(request(), MODEL, LLMResponse(text="x", input_tokens=1, output_tokens=1))

    with pytest.raises(MissingFixture):
        ReplayClient(store, "model-y").complete(request())


def test_two_requests_map_to_two_fixtures(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    other = request(messages=(Message(role="user", content="other"),))
    store.save(request(), MODEL, LLMResponse(text="one", input_tokens=1, output_tokens=1))
    store.save(other, MODEL, LLMResponse(text="two", input_tokens=2, output_tokens=2))

    client = ReplayClient(store, MODEL)

    assert client.complete(request()).text == "one"
    assert client.complete(other).text == "two"


def test_the_replay_client_satisfies_the_port(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    store.save(request(), MODEL, LLMResponse(text="x", input_tokens=1, output_tokens=1))
    client: LLMClient = ReplayClient(store, MODEL)

    assert client.complete(request()).text == "x"
