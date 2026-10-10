import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from importlib.metadata import version

_ERROR_BODY_LIMIT = 500


class HttpError(RuntimeError):
    pass


class HttpStatusError(HttpError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:_ERROR_BODY_LIMIT]}")
        self.status = status
        self.body = body


class HttpTimeout(HttpError):
    pass


def post_json(
    url: str,
    payload: Mapping[str, object],
    headers: Mapping[str, str],
    *,
    timeout: float,
) -> dict[str, object]:
    # urllib's default agent is rejected by some providers, so every request names this project.
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "user-agent": f"atda/{version('ai-test-design-agents')}",
            **headers,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body: dict[str, object] = json.loads(response.read())
            return body
    except urllib.error.HTTPError as error:
        raise HttpStatusError(error.code, error.read().decode(errors="replace")) from None
    except TimeoutError:
        raise HttpTimeout(f"no response from {url} within {timeout} s") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise HttpTimeout(f"no response from {url} within {timeout} s") from None
        raise HttpError(f"cannot reach {url}: {error.reason}") from None
