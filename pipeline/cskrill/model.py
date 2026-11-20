"""Turn raw LPDB rows into a small typed dataset with the queries prompts need.

LPDB's schema is only loosely documented and some fields arrive in more than
one shape (dict, JSON string, delimited string), so the parsers here are
defensive. Run `cskrill profile` on fresh data to see what you actually got.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .config import Config
from .countries import country_name
from .names import norm, page_to_label, team_name_variants

STAFF_ROLE_WORDS = ("coach", "analyst", "manager", "director", "owner", "ceo", "psycholog", "trainer")

# ---------------------------------------------------------------- parsers


def canon(title: Any) -> str:
    """Canonical MediaWiki page key: underscores for spaces, first letter upper-case."""
    t = " ".join(str(title or "").replace("_", " ").split())
    if not t:
        return ""
    return (t[0].upper() + t[1:]).replace(" ", "_")


def parse_date(v: Any) -> date | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    if y < 1980:  # LPDB uses 0000-00-00 / 1970-01-01 for "unknown"
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_int(v: Any) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def parse_place(v: Any) -> tuple[int, int] | None:
    """'1' -> (1, 1); '3-4' -> (3, 4); 'W'/'DQ'/'' -> None."""
    m = re.match(r"\s*(\d+)(?:st|nd|rd|th)?\s*(?:-\s*(\d+))?", str(v or ""))
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2) or lo)
    return (lo, hi) if lo > 0 else None


def as_mapping(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip().startswith("{"):
        try:
            d = json.loads(v)
        except ValueError:
            return {}
        return d if isinstance(d, dict) else {}
    return {}


def indexed_values(d: Mapping[str, Any], prefix: str) -> list[str]:
    """Values of keys `prefix`, `prefix1`, `prefix2`, ... in numeric order."""
    found = []
    for k, val in d.items():
        m = re.fullmatch(rf"{re.escape(prefix)}(\d*)", str(k))
        if m and val not in (None, ""):
            found.append((int(m.group(1) or 0), str(val).strip()))
    return [v for _, v in sorted(found)]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def as_name_list(v: Any, prefix: str | None = None) -> list[str]:
    """Organizers / maps: list, dict (organizer1, map1, ...), JSON string or 'a;b;c'."""
    if v in (None, ""):
        return []
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in "[{":
            try:
                return as_name_list(json.loads(s), prefix)
            except ValueError:
                pass
        items: list[Any] = re.split(r"[;|\n,]", s)
    elif isinstance(v, dict):
        vals = indexed_values(v, prefix) if prefix else []
        items = vals or list(v.values())
    elif isinstance(v, list):
        items = v
    else:
        return []
    out = []
    for it in items:
        if isinstance(it, dict):
            it = it.get("displayname") or it.get("name") or it.get("link") or it.get("map") or ""
        s = str(it).strip()
        if s:
            out.append(s)
    return _dedupe(out)


def parse_location(v: Any) -> tuple[str, str]:
    """(city, country) from {'city1': .., 'country1': ..} or 'City, Country'."""
    d = as_mapping(v)
    if d:
        cities = indexed_values(d, "city")
        countries = indexed_values(d, "country")
        return (cities[0] if cities else "", countries[0] if countries else "")
    if isinstance(v, str) and v.strip():
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[-1]
        return "", parts[0]
    return "", ""


def opponent_players(v: Any) -> list[tuple[str, str, str]]:
    """(page key, display name, flag) for each p1..pN in a placement's opponentplayers."""
    d = as_mapping(v)
    found = []
    for k, val in d.items():
        m = re.fullmatch(r"p(\d+)", str(k))
        if not m or not val:
            continue
        n = m.group(1)
        found.append((int(n), canon(val), str(d.get(f"p{n}dn") or val).strip(),
                      str(d.get(f"p{n}flag") or "").strip()))
    return [(key, dn, flag) for _, key, dn, flag in sorted(found) if key]


def age_on(birth: date, day: date) -> int:
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


# ---------------------------------------------------------------- records


@dataclass
class Player:
    key: str
    handle: str
    real_name: str = ""
    alt_ids: list[str] = field(default_factory=list)
    nationality: str = ""
    birthdate: date | None = None
    earnings: int = 0
    status: str = ""
    kind: str = ""  # LPDB `type`

    @property
    def is_player(self) -> bool:
        return self.kind.lower() in ("", "player")


@dataclass
class Team:
    key: str
    name: str
    template: str = ""
    region: str = ""
    earnings: int = 0
    status: str = ""


@dataclass
class Tournament:
    key: str
    name: str
    series: str = ""
    tier: str = ""
    publishertier: str = ""
    game: str = ""
    kind: str = ""  # Online / Offline
    start: date | None = None
    end: date | None = None
    city: str = ""
    country: str = ""
    organizers: list[str] = field(default_factory=list)
    maps: list[str] = field(default_factory=list)
    prizepool: float = 0.0
    is_major: bool = False
    top_level: bool = True

    @property
    def day(self) -> date | None:
        return self.end or self.start

    @property
    def offline(self) -> bool:
        return "offline" in self.kind.lower() or "lan" in self.kind.lower()


@dataclass
class Placement:
    tournament: str
    place: tuple[int, int] | None
    raw_place: str
    team: str
    players: list[str]
    day: date | None = None
    prize: int = 0

    @property
    def best(self) -> int | None:
        return self.place[0] if self.place else None


@dataclass
class SquadMember:
    team: str
    player: str
    role: str = ""
    position: str = ""
    kind: str = ""
    status: str = ""
    joined: date | None = None
    left: date | None = None

    @property
    def is_player_row(self) -> bool:
        if self.kind and self.kind.lower() not in ("player", "players"):
            return False
        role = f"{self.role} {self.position}".lower()
        return not any(w in role for w in STAFF_ROLE_WORDS)


# ---------------------------------------------------------------- dataset

LABEL_TYPES = ("city", "country", "organizer", "map")
ALIAS_SECTIONS = {"player": "players", "team": "teams", "city": "cities",
                  "country": "countries", "organizer": "organizers", "map": "maps"}


class Dataset:
    def __init__(self, cfg: Config, aliases: Mapping[str, Mapping[str, list[str]]] | None = None) -> None:
        self.cfg = cfg
        self.aliases = {k: dict(v) for k, v in (aliases or {}).items()}
        self.players: dict[str, Player] = {}
        self.teams: dict[str, Team] = {}
        self.tournaments: dict[str, Tournament] = {}
        self.placements: list[Placement] = []
        self.squads: list[SquadMember] = []
        self.labels: dict[str, dict[str, str]] = {t: {} for t in LABEL_TYPES}
        self._by_tournament: dict[str, list[Placement]] = defaultdict(list)
        self._team_lookup: dict[str, str] = {}
        self._label_lookup: dict[str, dict[str, str]] = {t: {} for t in LABEL_TYPES}
        self.latest: date | None = None
        self.recent_top4: dict[str, Counter[str]] = {"player": Counter(), "team": Counter()}
        self.label_counts: dict[str, Counter[str]] = {t: Counter() for t in LABEL_TYPES}
        self._seed_label_aliases()

    # ---- construction ---------------------------------------------------

    @classmethod
    def from_raw(cls, raw: Mapping[str, list[dict[str, Any]]], cfg: Config,
                 aliases: Mapping[str, Mapping[str, list[str]]] | None = None) -> "Dataset":
        ds = cls(cfg, aliases)
        for r in raw.get("player", []):
            ds._add_player(r)
        for r in raw.get("team", []):
            ds._add_team(r)
        ds._build_team_lookup()
        for r in raw.get("tournament", []):
            ds._add_tournament(r)
        ds._classify_tournaments()
        for r in raw.get("placement", []):
            ds._add_placement(r)
        for r in raw.get("squadplayer", []):
            ds._add_squad(r)
        ds._derive()
        return ds

    def _add_player(self, r: Mapping[str, Any]) -> None:
        key = canon(r.get("pagename") or r.get("id"))
        if not key:
            return
        alt = [a.strip() for a in re.split(r"[,;]", str(r.get("alternateid") or "")) if a.strip()]
        self.players[key] = Player(
            key=key,
            handle=str(r.get("id") or page_to_label(key)).strip(),
            real_name=str(r.get("name") or "").strip(),
            alt_ids=alt,
            nationality=str(r.get("nationality") or "").strip(),
            birthdate=parse_date(r.get("birthdate")),
            earnings=parse_int(r.get("earnings")),
            status=str(r.get("status") or "").strip(),
            kind=str(r.get("type") or "").strip(),
        )

    def _add_team(self, r: Mapping[str, Any]) -> None:
        key = canon(r.get("pagename") or r.get("name"))
        if not key:
            return
        self.teams[key] = Team(
            key=key,
            name=str(r.get("name") or page_to_label(key)).strip(),
            template=str(r.get("template") or "").strip(),
            region=str(r.get("region") or "").strip(),
            earnings=parse_int(r.get("earnings")),
            status=str(r.get("status") or "").strip(),
        )

    def _build_team_lookup(self) -> None:
        """norm(name) -> team key, used to resolve placement opponent names."""
        votes: dict[str, set[str]] = defaultdict(set)
        for t in self.teams.values():
            names = team_name_variants(t.name) | {page_to_label(t.key), t.template}
            names |= set(self.aliases.get("teams", {}).get(t.key, []))
            for n in names:
                if norm(n):
                    votes[norm(n)].add(t.key)
        self._team_lookup = {n: next(iter(ks)) for n, ks in votes.items() if len(ks) == 1}

    def resolve_team(self, name: str, template: str = "") -> str:
        key = canon(name)
        if key in self.teams:
            return key
        for candidate in (template, name):
            hit = self._team_lookup.get(norm(candidate)) if candidate else None
            if hit:
                return hit
        if key:
            self.teams[key] = Team(key=key, name=str(name).strip())
        return key

    def _add_tournament(self, r: Mapping[str, Any]) -> None:
        key = canon(r.get("pagename"))
        if not key:
            return
        city, country = parse_location(r.get("locations"))
        self.tournaments[key] = Tournament(
            key=key,
            name=str(r.get("name") or page_to_label(key)).strip(),
            series=str(r.get("seriespage") or "").strip(),
            tier=str(r.get("liquipediatier") or "").strip(),
            publishertier=str(r.get("publishertier") or "").strip(),
            game=str(r.get("game") or "").strip().lower(),
            kind=str(r.get("type") or "").strip(),
            start=parse_date(r.get("startdate")),
            end=parse_date(r.get("enddate")) or parse_date(r.get("sortdate")),
            city=self.label_key("city", city) if city else "",
            country=self.label_key("country", country_name(country)) if country else "",
            organizers=[self.label_key("organizer", o) for o in as_name_list(r.get("organizers"), "organizer")],
            maps=[self.label_key("map", m) for m in as_name_list(r.get("maps"), "map")],
            prizepool=float(r.get("prizepool") or 0),
        )

    def _classify_tournaments(self) -> None:
        keys = set(self.tournaments)
        include, exclude = set(map(canon, self.cfg.majors_include)), set(map(canon, self.cfg.majors_exclude))
        for t in self.tournaments.values():
            parts = t.key.split("/")
            t.top_level = not any("/".join(parts[:i]) in keys for i in range(1, len(parts)))
            if t.key in include:
                t.is_major = True
            elif t.key in exclude:
                t.is_major = False
            else:
                t.is_major = looks_like_major(t)

    def _add_placement(self, r: Mapping[str, Any]) -> None:
        if str(r.get("opponenttype") or "team").lower() not in ("team", ""):
            return
        tkey = canon(r.get("pagename") or r.get("parent") or r.get("tournament"))
        team = self.resolve_team(str(r.get("opponentname") or ""), str(r.get("opponenttemplate") or ""))
        players = []
        for key, display, flag in opponent_players(r.get("opponentplayers")):
            p = self.players.get(key)
            if p is None:
                p = self.players[key] = Player(key=key, handle=display or page_to_label(key), nationality=flag)
            elif not p.nationality and flag:
                p.nationality = flag
            players.append(key)
        pl = Placement(
            tournament=tkey,
            place=parse_place(r.get("placement")),
            raw_place=str(r.get("placement") or ""),
            team=team,
            players=players,
            day=parse_date(r.get("date")) or parse_date(r.get("startdate")),
            prize=parse_int(r.get("prizemoney")),
        )
        self.placements.append(pl)
        self._by_tournament[tkey].append(pl)

    def _add_squad(self, r: Mapping[str, Any]) -> None:
        team = canon(r.get("pagename"))
        player = canon(r.get("link") or r.get("id"))
        if not team or not player:
            return
        if player not in self.players:
            self.players[player] = Player(
                key=player,
                handle=str(r.get("id") or page_to_label(player)).strip(),
                real_name=str(r.get("name") or "").strip(),
                nationality=str(r.get("nationality") or "").strip(),
            )
        if team not in self.teams:
            self.teams[team] = Team(key=team, name=page_to_label(team))
        self.squads.append(SquadMember(
            team=team,
            player=player,
            role=str(r.get("role") or "").strip(),
            position=str(r.get("position") or "").strip(),
            kind=str(r.get("type") or "").strip(),
            status=str(r.get("status") or "").strip(),
            joined=parse_date(r.get("joindate")),
            left=parse_date(r.get("leavedate")) or parse_date(r.get("inactivedate")),
        ))

    def _derive(self) -> None:
        days = [t.day for t in self.tournaments.values() if t.day]
        self.latest = max(days) if days else None
        cutoff = (self.latest - timedelta(days=365 * self.cfg.recent_years)) if self.latest else None
        for t in self.events(tier="1"):
            for kind, value in (("city", [t.city]), ("country", [t.country]),
                                ("organizer", t.organizers), ("map", t.maps)):
                for v in set(filter(None, value)):
                    self.label_counts[kind][v] += 1
            if self.is_stage(t) or not (cutoff and t.day and t.day >= cutoff):
                continue
            for pl in self.placements_at(t.key):
                if pl.best is not None and pl.best <= 4:
                    self.recent_top4["team"][pl.team] += 1
                    for p in pl.players:
                        self.recent_top4["player"][p] += 1

    # ---- labels (cities, countries, organizers, maps) -------------------

    def _seed_label_aliases(self) -> None:
        for kind in LABEL_TYPES:
            for label, extra in self.aliases.get(ALIAS_SECTIONS[kind], {}).items():
                key = canon(label)
                self.labels[kind].setdefault(key, page_to_label(label))
                for name in [label, *extra]:
                    if norm(name):
                        self._label_lookup[kind][norm(name)] = key

    def label_key(self, kind: str, raw: str) -> str:
        """Canonical key for a free-text label, merging spellings via aliases.yaml."""
        name = raw.strip().replace("_", " ")
        if kind == "map" and name.lower().startswith("de "):
            name = name[3:]
        n = norm(name)
        if not n:
            return ""
        key = self._label_lookup[kind].get(n)
        if key is None:
            key = canon(name)
            self._label_lookup[kind][n] = key
        self.labels[kind].setdefault(key, name)
        return key

    # ---- queries used by prompt builders --------------------------------

    def in_era(self, t: Tournament) -> bool:
        if t.day and t.day < self.cfg.era_start:
            return False
        if self.cfg.games and t.game and t.game not in self.cfg.games:
            return False
        return True

    def is_stage(self, t: Tournament) -> bool:
        last = t.key.rsplit("/", 1)[-1].lower()
        return any(w in last for w in self.cfg.stage_words)

    def events(self, *, tier: str | None = None, major: bool | None = None,
               since: date | None = None, top_level: bool = True) -> list[Tournament]:
        out = []
        for t in self.tournaments.values():
            if not self.in_era(t) or (top_level and not t.top_level):
                continue
            if tier is not None and t.tier != tier:
                continue
            if major is not None and t.is_major != major:
                continue
            if since and not (t.day and t.day >= since):
                continue
            out.append(t)
        return sorted(out, key=lambda t: (t.day or date.min, t.key))

    def major_events(self) -> list[Tournament]:
        return self.events(major=True)

    def placements_at(self, tournament_key: str) -> list[Placement]:
        return self._by_tournament.get(tournament_key, [])

    def finishers(self, events: Iterable[Tournament], max_place: int) -> tuple[set[str], set[str]]:
        """(players, teams) whose best placement at any of `events` is <= max_place."""
        players: set[str] = set()
        teams: set[str] = set()
        for t in events:
            for pl in self.placements_at(t.key):
                if pl.best is not None and pl.best <= max_place:
                    players.update(pl.players)
                    if pl.team:
                        teams.add(pl.team)
        return players, teams

    def display(self, etype: str, key: str) -> str:
        if etype == "player" and key in self.players:
            return self.players[key].handle
        if etype == "team" and key in self.teams:
            return self.teams[key].name
        if etype in self.labels:
            return self.labels[etype].get(key, page_to_label(key))
        return page_to_label(key)


# Liquipedia's CS module stores Valve tiers by display name: "Major Championship",
# "Major Qualifier", "Minor Championship", "RMR Event", "Tier 1", ...
MAJOR_PUBLISHER_TIERS = frozenset({"major championship", "major"})


def looks_like_major(t: Tournament) -> bool:
    """Valve Major detection. Check the list `cskrill profile` prints and use
    events.majors_include / majors_exclude in config.yaml to fix mistakes."""
    tier = t.publishertier.strip().lower()
    if tier:
        return tier in MAJOR_PUBLISHER_TIERS
    name = t.name.lower()  # fallback for pages without a Valve tier
    if re.search(r"qualifier|\brmr\b|minor|closed|last chance", name):
        return False
    return t.tier == "1" and re.search(r"\bmajor\b", name) is not None
