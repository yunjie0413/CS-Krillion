"""`cskrill profile`: show what the raw data actually looks like.

Run this after the first fetch. It prints the value distributions and field
shapes the parsers depend on, plus the list of events detected as Majors, so
wrong assumptions show up before they turn into wrong answers.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .config import Config
from .countries import is_unmapped_code
from .model import Dataset, canon, parse_location


def _dist(rows: list[dict], field: str, top: int = 15) -> str:
    c = Counter(str(r.get(field) if r.get(field) not in (None, "") else "(empty)") for r in rows)
    shown = ", ".join(f"{k} x{v}" for k, v in c.most_common(top))
    more = f"  (+{len(c) - top} more)" if len(c) > top else ""
    return f"  {field}: {shown}{more}"


def _samples(rows: list[dict], field: str, n: int = 3) -> list[str]:
    out = []
    for r in rows:
        v = r.get(field)
        if v not in (None, "", {}, []):
            out.append(f"  {field} = {json.dumps(v, ensure_ascii=False)[:160]}")
        if len(out) >= n:
            break
    return out or [f"  {field}: (always empty)"]


def profile_report(raw: Mapping[str, list[dict[str, Any]]], cfg: Config,
                   aliases: Mapping[str, Mapping[str, list[str]]] | None = None) -> str:
    t_rows, p_rows = raw.get("tournament", []), raw.get("placement", [])
    pl_rows, tm_rows, sq_rows = raw.get("player", []), raw.get("team", []), raw.get("squadplayer", [])
    out = ["== Row counts"]
    out += [f"  {k}: {len(v)}" for k, v in raw.items()]

    out += ["", "== Tournaments"]
    out += [_dist(t_rows, f) for f in ("game", "liquipediatier", "publishertier", "type")]
    for f in ("locations", "organizers", "maps"):
        out += _samples(t_rows, f)
    codes = Counter(c for c in (parse_location(r.get("locations"))[1] for r in t_rows) if c and is_unmapped_code(c))
    if codes:
        out.append("  !! country codes missing from cskrill/countries.py: "
                   + ", ".join(f"{c} x{n}" for c, n in codes.most_common()))

    out += ["", "== Placements"]
    out += [_dist(p_rows, f, 20) for f in ("placement", "opponenttype")]
    out += _samples(p_rows, "opponentplayers", 2)

    out += ["", "== Players"]
    out += [_dist(pl_rows, f) for f in ("type", "status")]
    out += _samples(pl_rows, "alternateid", 3)

    out += ["", "== Teams", _dist(tm_rows, "status")]

    if sq_rows or cfg.squad_teams:
        out += ["", "== Squad rows"]
        out += [_dist(sq_rows, f) for f in ("type", "status", "role", "position")]
        found = {canon(r.get("pagename")) for r in sq_rows}
        missing = [t for t in cfg.squad_teams if canon(t) not in found]
        if missing:
            out.append(f"  !! no rows for: {', '.join(missing)} (check page names)")

    ds = Dataset.from_raw(raw, cfg, aliases)
    excluded = Counter(t.game or "(empty)" for t in ds.tournaments.values() if not ds.in_era(t))
    out += ["", "== Era filter",
            f"  keeping games {list(cfg.games) or 'all'} from {cfg.era_start}",
            "  excluded by era/game: " + (", ".join(f"{g} x{n}" for g, n in excluded.most_common()) or "none")]

    out += ["", "== Detected Majors (top-level pages only). Check this list!"]
    for t in ds.major_events():
        winners = [pl for pl in ds.placements_at(t.key) if pl.best == 1]
        champ = ds.display("team", winners[0].team) if winners else "?? no 1st-place row"
        city = ds.display("city", t.city) if t.city else "?"
        out.append(f"  {t.day}  {t.name:<45} {city:<16} winner: {champ}  "
                   f"({len(ds.placements_at(t.key))} placements)")
    suspicious = [t for t in ds.events(tier="1") if not t.is_major and "major" in t.name.lower()]
    if suspicious:
        out.append("  Not counted as Majors although the name says Major (add to majors_include if wrong):")
        out += [f"    {t.key}" for t in suspicious]
    return "\n".join(out)
