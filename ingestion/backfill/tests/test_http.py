import io
import urllib.error

import pytest

from backfill.http import USER_AGENT, HttpError, RateLimitedClient


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, retry_after=None):
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return urllib.error.HTTPError("https://x.test", code, "err", headers, None)


def scripted_opener(script):
    """Each call pops the next item: bytes -> response, Exception -> raised."""
    requests = []

    def opener(request, timeout):
        requests.append(request)
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return Response(item)

    opener.requests = requests
    return opener


def make_client(script, min_interval=1.0, **kw):
    clock = FakeClock()
    opener = scripted_opener(script)
    client = RateLimitedClient(min_interval, clock=clock, sleep=clock.sleep, opener=opener, **kw)
    return client, clock, opener


def test_spaces_requests_by_min_interval():
    client, clock, _ = make_client([b"a", b"b", b"c"], min_interval=8.0)
    for _ in range(3):
        client.get_bytes("https://x.test")
    assert clock.sleeps == [8.0, 8.0]
    assert client.requests_made == 3


def test_no_wait_when_interval_already_passed():
    client, clock, _ = make_client([b"a", b"b"], min_interval=2.0)
    client.get_bytes("https://x.test")
    clock.now += 5
    client.get_bytes("https://x.test")
    assert clock.sleeps == []


def test_sends_identifying_user_agent():
    client, _, opener = make_client([b"{}"])
    client.get_json("https://x.test")
    assert opener.requests[0].get_header("User-agent") == USER_AGENT


def test_retries_429_honouring_retry_after():
    client, clock, _ = make_client([http_error(429, retry_after=30), b'{"ok": true}'], min_interval=0)
    assert client.get_json("https://x.test") == {"ok": True}
    assert 30.0 in clock.sleeps


def test_retries_5xx_with_exponential_backoff():
    client, clock, _ = make_client([http_error(503), http_error(503), b"ok"], min_interval=0, backoff_base=1.0)
    assert client.get_bytes("https://x.test") == b"ok"
    assert clock.sleeps == [1.0, 2.0]


def test_retries_network_errors():
    client, _, _ = make_client([urllib.error.URLError("reset"), b"ok"], min_interval=0, backoff_base=0)
    assert client.get_bytes("https://x.test") == b"ok"


def test_does_not_retry_404():
    client, _, opener = make_client([http_error(404)], min_interval=0)
    with pytest.raises(HttpError) as exc:
        client.get_bytes("https://x.test")
    assert exc.value.status == 404
    assert len(opener.requests) == 1


def test_gives_up_after_max_retries():
    client, _, opener = make_client([http_error(429)] * 3, min_interval=0, max_retries=2, backoff_base=0)
    with pytest.raises(HttpError):
        client.get_bytes("https://x.test")
    assert len(opener.requests) == 3
