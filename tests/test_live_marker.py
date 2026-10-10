import os
import subprocess
import sys
from pathlib import Path

LIVE_TEST = Path(__file__).parent / "test_anthropic_live.py"


def run_pytest(*args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args, str(LIVE_TEST)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result.stdout


def test_the_live_test_is_deselected_by_default() -> None:
    assert "1 deselected" in run_pytest("--collect-only")


def test_the_live_test_is_selected_by_the_marker() -> None:
    assert "test_anthropic_live.py::test_" in run_pytest("--collect-only", "-m", "live")


def test_the_live_test_skips_with_a_clear_message_without_a_key() -> None:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    output = run_pytest("-rs", "-m", "live", env=env)

    assert "ANTHROPIC_API_KEY is not set; the live test needs a key" in output
