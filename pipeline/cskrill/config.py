"""Configuration: a flat dataclass loaded from the nested config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Tier:
    name: str
    points: int
    min_share: float  # an answer lands in the first tier whose min_share <= its share


DEFAULT_TIERS: tuple[Tier, ...] = (
    Tier("Silver", 10, 0.10),
    Tier("Gold Nova", 25, 0.05),
    Tier("Master Guardian", 40, 0.025),
    Tier("Legendary Eagle", 60, 0.01),
    Tier("Supreme", 80, 0.004),
    Tier("Global Elite", 100, 0.0),
)

# A tournament page whose last path segment contains one of these is a stage or
# side event, so finishing 1st there doesn't count as winning the event.
DEFAULT_STAGE_WORDS: tuple[str, ...] = (
    "qualifier", "play-in", "playin", "groups", "group_stage", "stage",
    "showmatch", "last_chance", "rmr",
)


@dataclass(frozen=True)
class Config:
    # identity and API
    user_agent: str = ""
    wiki: str = "counterstrike"
    min_interval_s: float = 4.0
    max_retries: int = 5
    page_size: int = 1000
    # era
    era_start: date = date(2012, 8, 21)
    cs2_release: date = date(2023, 9, 27)
    games: tuple[str, ...] = ("csgo", "csgocs2", "cs2")
    # fetch scope
    tournament_tiers: tuple[str, ...] = ("1", "2")
    placement_tiers: tuple[str, ...] = ("1", "2")
    min_player_earnings: int = 1000
    min_team_earnings: int = 10000
    squad_teams: tuple[str, ...] = ()
    # event classification
    majors_include: tuple[str, ...] = ()
    majors_exclude: tuple[str, ...] = ()
    stage_words: tuple[str, ...] = DEFAULT_STAGE_WORDS
    # prompts
    min_answers: int = 10
    min_answers_small: int = 6
    earnings_threshold: int = 1_000_000
    many_majors: int = 10
    # rarity
    temperature: float = 2.0
    recent_years: int = 3
    recent_weight: float = 0.4
    live_prior_strength: float = 200.0
    tiers: tuple[Tier, ...] = DEFAULT_TIERS
    # matching
    accept_real_names: bool = True
    fuzzy: bool = True
    extra: dict[str, Any] = field(default_factory=dict, compare=False)

    def with_overrides(self, **kw: Any) -> "Config":
        return replace(self, **kw)


def _date(v: Any, default: date) -> date:
    if v in (None, ""):
        return default
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _strs(v: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if v is None:
        return default
    return tuple(str(x).strip() for x in v if str(x).strip())


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    return config_from_dict(raw)


def config_from_dict(raw: dict[str, Any]) -> Config:
    d = Config()
    api = raw.get("api") or {}
    era = raw.get("era") or {}
    fetch = raw.get("fetch") or {}
    events = raw.get("events") or {}
    prompts = raw.get("prompts") or {}
    rarity = raw.get("rarity") or {}
    matching = raw.get("matching") or {}

    tiers = d.tiers
    if rarity.get("tiers"):
        tiers = tuple(
            Tier(str(t["name"]), int(t["points"]), float(t["min_share"])) for t in rarity["tiers"]
        )
        tiers = tuple(sorted(tiers, key=lambda t: -t.min_share))
        if tiers[-1].min_share > 0:
            raise ValueError("The last rarity tier must have min_share: 0 so every answer gets a tier.")

    return Config(
        user_agent=str(raw.get("user_agent", d.user_agent)),
        wiki=str(raw.get("wiki", d.wiki)),
        min_interval_s=float(api.get("min_interval_s", d.min_interval_s)),
        max_retries=int(api.get("max_retries", d.max_retries)),
        page_size=int(api.get("page_size", d.page_size)),
        era_start=_date(era.get("start"), d.era_start),
        cs2_release=_date(era.get("cs2_release"), d.cs2_release),
        games=tuple(g.lower() for g in _strs(era.get("games"), d.games)),
        tournament_tiers=_strs(fetch.get("tournament_tiers"), d.tournament_tiers),
        placement_tiers=_strs(fetch.get("placement_tiers"), d.placement_tiers),
        min_player_earnings=int(fetch.get("min_player_earnings", d.min_player_earnings)),
        min_team_earnings=int(fetch.get("min_team_earnings", d.min_team_earnings)),
        squad_teams=_strs(fetch.get("squad_teams"), d.squad_teams),
        majors_include=_strs(events.get("majors_include"), d.majors_include),
        majors_exclude=_strs(events.get("majors_exclude"), d.majors_exclude),
        stage_words=tuple(w.lower() for w in _strs(events.get("stage_words"), d.stage_words)),
        min_answers=int(prompts.get("min_answers", d.min_answers)),
        min_answers_small=int(prompts.get("min_answers_small", d.min_answers_small)),
        earnings_threshold=int(prompts.get("earnings_threshold", d.earnings_threshold)),
        many_majors=int(prompts.get("many_majors", d.many_majors)),
        temperature=float(rarity.get("temperature", d.temperature)),
        recent_years=int(rarity.get("recent_years", d.recent_years)),
        recent_weight=float(rarity.get("recent_weight", d.recent_weight)),
        live_prior_strength=float(rarity.get("live_prior_strength", d.live_prior_strength)),
        tiers=tiers,
        accept_real_names=bool(matching.get("accept_real_names", d.accept_real_names)),
        fuzzy=bool(matching.get("fuzzy", d.fuzzy)),
        extra=raw,
    )


def load_aliases(path: str | Path | None) -> dict[str, dict[str, list[str]]]:
    """aliases.yaml: {etype: {canonical key or label: [extra names]}}."""
    if not path or not Path(path).exists():
        return {}
    raw = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    out: dict[str, dict[str, list[str]]] = {}
    for etype, mapping in raw.items():
        out[str(etype)] = {
            str(k): [str(a) for a in (v or [])] for k, v in (mapping or {}).items()
        }
    return out
