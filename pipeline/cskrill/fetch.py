"""Download the LPDB tables the prompts need into data/raw/<table>.json.

Rough cost of a full run with the default config: about 50 to 90 requests,
which takes several minutes at the default throttle. Everything is cached, so
a second run is free unless you pass --refresh.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from .config import Config
from .lpdb import LpdbClient, dedupe_rows
from .model import canon

log = logging.getLogger(__name__)

TOURNAMENT_FIELDS = [
    "pagename", "name", "shortname", "tickername", "seriespage", "game", "type", "organizers",
    "startdate", "enddate", "sortdate", "locations", "prizepool", "participantsnumber",
    "liquipediatier", "liquipediatiertype", "publishertier", "status", "maps",
]
PLACEMENT_FIELDS = [
    "pagename", "tournament", "parent", "series", "placement", "date", "startdate", "prizemoney",
    "liquipediatier", "liquipediatiertype", "publishertier", "game", "mode", "type",
    "opponentname", "opponenttemplate", "opponenttype", "opponentplayers",
]
PLAYER_FIELDS = [
    "pagename", "id", "alternateid", "name", "localizedname", "type", "nationality",
    "nationality2", "region", "birthdate", "status", "earnings", "teampagename",
]
TEAM_FIELDS = [
    "pagename", "name", "region", "locations", "status", "createdate", "disbanddate",
    "earnings", "template",
]
SQUAD_FIELDS = [
    "pagename", "id", "link", "name", "nationality", "position", "role", "type", "status",
    "joindate", "leavedate", "inactivedate", "teamtemplate",
]


@dataclass(frozen=True)
class Job:
    name: str
    fields: list[str]
    conditions: list[str]  # one fetch per condition string; results are merged


def any_of(field: str, values: list[str] | tuple[str, ...]) -> str:
    clauses = [f"[[{field}::{v}]]" for v in values]
    return clauses[0] if len(clauses) == 1 else "(" + " OR ".join(clauses) + ")"


def batched(values: list[str] | tuple[str, ...], size: int) -> list[list[str]]:
    return [list(values[i:i + size]) for i in range(0, len(values), size)]


def plan(cfg: Config) -> list[Job]:
    since = (cfg.era_start - timedelta(days=1)).isoformat()
    jobs = [
        Job("tournament", TOURNAMENT_FIELDS,
            [f"{any_of('liquipediatier', cfg.tournament_tiers)} AND [[sortdate::>{since}]]"]),
        Job("placement", PLACEMENT_FIELDS,
            [f"{any_of('liquipediatier', cfg.placement_tiers)} AND [[date::>{since}]]"]),
        Job("player", PLAYER_FIELDS, [f"[[earnings::>{max(0, cfg.min_player_earnings - 1)}]]"]),
        Job("team", TEAM_FIELDS, [f"[[earnings::>{max(0, cfg.min_team_earnings - 1)}]]"]),
    ]
    if cfg.squad_teams:
        pages = [canon(t) for t in cfg.squad_teams]
        jobs.append(Job("squadplayer", SQUAD_FIELDS, [any_of("pagename", b) for b in batched(pages, 8)]))
    return jobs


def run_fetch(client: LpdbClient, cfg: Config, raw_dir: Path, *,
              tables: set[str] | None = None, refresh: bool = False) -> dict[str, int]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for job in plan(cfg):
        if tables and job.name not in tables:
            continue
        rows = []
        for cond in job.conditions:
            rows += client.fetch_all(job.name, wiki=cfg.wiki, fields=job.fields, conditions=cond,
                                     page_size=cfg.page_size, refresh=refresh)
        rows = dedupe_rows(rows)
        (raw_dir / f"{job.name}.json").write_text(json.dumps(rows, ensure_ascii=False), "utf-8")
        counts[job.name] = len(rows)
        log.info("%-12s %6d rows  (API calls so far: %d, cache hits: %d)",
                 job.name, len(rows), client.requests_made, client.cache_hits)

    if "squadplayer" in counts:
        rows = json.loads((raw_dir / "squadplayer.json").read_text("utf-8"))
        found = {canon(r.get("pagename")) for r in rows}
        for team in cfg.squad_teams:
            if canon(team) not in found:
                log.warning("No roster rows for %r: check the exact Liquipedia page name.", team)

    manifest = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wiki": cfg.wiki,
        "counts": counts,
        "api_requests": client.requests_made,
        "cache_hits": client.cache_hits,
        "source": "Liquipedia (https://liquipedia.net), CC-BY-SA 3.0",
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return counts


def load_raw(raw_dir: Path) -> dict[str, list[dict]]:
    raw: dict[str, list[dict]] = {}
    for name in ("tournament", "placement", "player", "team", "squadplayer"):
        path = raw_dir / f"{name}.json"
        raw[name] = json.loads(path.read_text("utf-8")) if path.exists() else []
    return raw
