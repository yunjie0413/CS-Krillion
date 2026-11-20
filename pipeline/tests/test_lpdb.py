import json

import pytest

from cskrill.lpdb import LpdbClient, LpdbError, dedupe_rows


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {"result": []}
        self.headers = headers or {}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    """Answers each GET from a function of the request params."""

    def __init__(self, responder):
        self.responder = responder
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers or {})})
        return self.responder(dict(params))


def make_client(responder, tmp_path=None, **kw):
    session = FakeSession(responder)
    sleeps = []
    client = LpdbClient("KEY", "Test/1.0 (https://example.org; me@example.org)",
                        tmp_path, session=session, sleep=sleeps.append, clock=lambda: 0.0, **kw)
    return client, session, sleeps


def test_rejects_placeholder_user_agent():
    with pytest.raises(ValueError):
        LpdbClient("KEY", "CS2Krillion (https://github.com/YOUR_GITHUB/x; YOUR_EMAIL)")


def test_auth_header_user_agent_and_gzip():
    client, session, _ = make_client(lambda p: FakeResponse(body={"result": [{"pageid": 1}]}))
    client.get("player", {"wiki": "counterstrike"})
    call = session.calls[0]
    assert call["url"] == "https://api.liquipedia.net/api/v3/player"
    assert call["headers"]["Authorization"] == "Apikey KEY"
    assert session.headers["User-Agent"].startswith("Test/1.0")
    assert session.headers["Accept-Encoding"] == "gzip"


def test_throttle_waits_between_requests():
    client, _, sleeps = make_client(lambda p: FakeResponse(), min_interval=4.0)
    client.get("player", {"offset": 0})
    client.get("player", {"offset": 1})
    assert sleeps == [4.0]


def test_retries_429_using_retry_after():
    responses = iter([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(body={"result": [{"x": 1}]})])
    client, session, sleeps = make_client(lambda p: next(responses), min_interval=0)
    assert client.get("player", {}) == [{"x": 1}]
    assert 7.0 in sleeps and len(session.calls) == 2


def test_error_envelope_and_auth_failure_raise():
    client, _, _ = make_client(lambda p: FakeResponse(body={"error": ["Unknown field: foo"]}))
    with pytest.raises(LpdbError, match="Unknown field"):
        client.get("player", {})
    client, _, _ = make_client(lambda p: FakeResponse(403, body={"error": ["bad key"]}))
    with pytest.raises(LpdbError, match="403"):
        client.get("player", {})


def test_cache_avoids_second_request(tmp_path):
    client, session, _ = make_client(lambda p: FakeResponse(body={"result": [{"a": 1}]}), tmp_path)
    assert client.get("team", {"wiki": "counterstrike"}) == [{"a": 1}]
    assert client.get("team", {"wiki": "counterstrike"}) == [{"a": 1}]
    assert len(session.calls) == 1 and client.cache_hits == 1
    cached = next(tmp_path.rglob("*.json"))
    assert json.loads(cached.read_text())["params"] == {"wiki": "counterstrike"}


def test_no_key_and_no_cache_explains():
    client = LpdbClient(None, "Test/1.0 (https://example.org; me@example.org)")
    with pytest.raises(LpdbError, match="LIQUIPEDIA_API_KEY"):
        client.get("player", {})


def test_fetch_all_pages_and_repairs_tie_at_page_boundary():
    # 5 rows; pageid 2 has three rows that straddle the first page boundary.
    table = [{"pageid": 1, "objectname": "a"}, {"pageid": 2, "objectname": "b"},
             {"pageid": 2, "objectname": "c"}, {"pageid": 2, "objectname": "d"},
             {"pageid": 3, "objectname": "e"}]
    served = {"n": 0}

    def responder(p):
        cond = p.get("conditions") or ""
        if "[[pageid::2]]" in cond:
            return FakeResponse(body={"result": [r for r in table if r["pageid"] == 2]})
        served["n"] += 1
        # Simulate unstable tie order: the 2nd page repeats row "c" and never shows "d".
        pages = {0: table[0:2] + [table[2]], 3: [table[2], table[4]]}
        return FakeResponse(body={"result": pages[p["offset"]]})

    client, session, _ = make_client(responder, min_interval=0)
    rows = client.fetch_all("placement", wiki="counterstrike", fields=["pagename"], page_size=3)
    assert sorted(r["objectname"] for r in rows) == ["a", "b", "c", "d", "e"]
    assert "objectname" in session.calls[0]["params"]["query"]
    assert session.calls[0]["params"]["order"] == "pageid ASC"


def test_dedupe_rows_without_ids_uses_content():
    assert len(dedupe_rows([{"x": 1}, {"x": 1}, {"x": 2}])) == 2
