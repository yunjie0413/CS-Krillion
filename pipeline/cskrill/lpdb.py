"""Small LiquipediaDB (LPDB) v3 client.

Built to the rules in https://liquipedia.net/api-terms-of-use:
  * a custom User-Agent that names the project and gives contact info,
  * gzip, and one reused connection,
  * throttled requests with backoff on HTTP 429,
  * every response cached on disk "for as long as possible", so re-runs and
    rebuilds cost no API calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.liquipedia.net/api/v3/"
MAX_PAGE = 1000  # LPDB's maximum `limit`

log = logging.getLogger(__name__)

Row = dict[str, Any]


class LpdbError(RuntimeError):
    """The API returned an error envelope, an auth failure, or kept failing."""


class LpdbClient:
    def __init__(
        self,
        api_key: str | None,
        user_agent: str,
        cache_dir: str | Path | None = None,
        *,
        min_interval: float = 4.0,
        max_retries: int = 5,
        timeout: float = 60.0,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not user_agent or "YOUR_" in user_agent:
            raise ValueError(
                "Set LIQUIPEDIA_USER_AGENT (or user_agent in config.yaml) to your project URL "
                "and email. Liquipedia blocks generic or anonymous agents."
            )
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip"})
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.requests_made = 0
        self.cache_hits = 0

    # ---- single request -------------------------------------------------

    def get(self, endpoint: str, params: Mapping[str, Any], *, refresh: bool = False) -> list[Row]:
        """One API call (or cache hit). Returns the `result` list."""
        params = {k: v for k, v in params.items() if v not in (None, "")}
        path = self._cache_path(endpoint, params)
        if path is not None and path.exists() and not refresh:
            self.cache_hits += 1
            return json.loads(path.read_text("utf-8"))["result"]
        if not self.api_key:
            raise LpdbError(
                f"No cached data for /{endpoint} and no API key. Set LIQUIPEDIA_API_KEY."
            )
        body = self._request(endpoint, params)
        for warning in body.get("warning") or []:
            log.warning("LPDB warning on /%s: %s", endpoint, warning)
        result = body.get("result")
        if not isinstance(result, list):
            raise LpdbError(f"/{endpoint}: response has no 'result' list: {str(body)[:200]}")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "endpoint": endpoint,
                "params": params,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "result": result,
            }
            path.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        return result

    def _request(self, endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
        url = BASE_URL + endpoint.strip("/")
        headers = {"Authorization": f"Apikey {self.api_key}"}
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            self._throttle()
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if last:
                    raise LpdbError(f"/{endpoint}: network error after {attempt + 1} tries: {exc}") from exc
                self._sleep(self._backoff(attempt))
                continue
            self.requests_made += 1

            if resp.status_code == 429 or resp.status_code >= 500:
                if last:
                    raise LpdbError(f"/{endpoint}: HTTP {resp.status_code} after {attempt + 1} tries")
                wait = _retry_after(resp) or self._backoff(attempt)
                log.warning("HTTP %s from LPDB, waiting %.0fs", resp.status_code, wait)
                self._sleep(wait)
                continue
            if resp.status_code in (401, 403):
                raise LpdbError(
                    f"/{endpoint}: HTTP {resp.status_code}. Check LIQUIPEDIA_API_KEY and that your "
                    "plan covers this endpoint and wiki."
                )
            try:
                body = resp.json()
            except ValueError as exc:
                raise LpdbError(f"/{endpoint}: HTTP {resp.status_code}, body is not JSON") from exc
            if body.get("error"):
                errors = body["error"] if isinstance(body["error"], list) else [body["error"]]
                raise LpdbError(f"/{endpoint}: " + "; ".join(map(str, errors)))
            if resp.status_code != 200:
                raise LpdbError(f"/{endpoint}: unexpected HTTP {resp.status_code}")
            return body
        raise AssertionError("unreachable")

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(300.0, 5.0 * 2**attempt)

    def _cache_path(self, endpoint: str, params: Mapping[str, Any]) -> Path | None:
        if self.cache_dir is None:
            return None
        key = json.dumps([endpoint, sorted((k, str(v)) for k, v in params.items())])
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        return self.cache_dir / endpoint.strip("/") / f"{digest}.json"

    # ---- whole tables ----------------------------------------------------

    def fetch_all(
        self,
        endpoint: str,
        *,
        wiki: str,
        fields: list[str],
        conditions: str | None = None,
        order: str = "pageid ASC",
        page_size: int = MAX_PAGE,
        refresh: bool = False,
    ) -> list[Row]:
        """Every row matching `conditions`, paged with limit/offset.

        LPDB sorts by a single field, and rows that tie on it can come back in a
        different order on each request, so a tie group split across two pages
        could lose or repeat rows. After paging we re-request each page's last
        `pageid` on its own (cheap: one call per full page) and de-duplicate on
        (pageid, objectname), which is unique per row.
        """
        page_size = max(1, min(page_size, MAX_PAGE))
        query = ", ".join(sorted(set(fields) | {"pageid", "objectname"}))
        base = {"wiki": wiki, "query": query, "order": order, "limit": page_size}

        rows: list[Row] = []
        boundary_ids: set[Any] = set()
        offset = 0
        while True:
            page = self.get(endpoint, {**base, "conditions": conditions, "offset": offset}, refresh=refresh)
            rows.extend(page)
            if len(page) < page_size:
                break
            boundary_ids.add(page[-1].get("pageid"))
            offset += page_size

        for pid in sorted(p for p in boundary_ids if p not in (None, "")):
            cond = f"[[pageid::{pid}]]" if not conditions else f"({conditions}) AND [[pageid::{pid}]]"
            rows.extend(self.get(endpoint, {**base, "conditions": cond, "offset": 0}, refresh=refresh))
        return dedupe_rows(rows)


def dedupe_rows(rows: list[Row]) -> list[Row]:
    seen: set[Any] = set()
    out: list[Row] = []
    for r in rows:
        if r.get("pageid") not in (None, "") and r.get("objectname") not in (None, ""):
            key: Any = (r["pageid"], r["objectname"])
        else:
            key = json.dumps(r, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _retry_after(resp: requests.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
