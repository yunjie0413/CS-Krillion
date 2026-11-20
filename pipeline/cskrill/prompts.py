"""Prompt builders: each turns the dataset into one or more prompts with answer sets.

To add a prompt, write a generator that takes (ds, cfg), yields Prompt objects,
and decorate it with @builder. Prompts with fewer than `min_answers` valid
answers are dropped at build time (and listed in the build report).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .config import Config
from .model import Dataset, age_on


@dataclass
class Prompt:
    id: str
    text: str
    etype: str  # player | team | city | country | organizer | map
    answers: set[str]
    min_answers: int


Builder = Callable[[Dataset, Config], Iterator[Prompt]]
REGISTRY: list[Builder] = []


def builder(fn: Builder) -> Builder:
    REGISTRY.append(fn)
    return fn


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def article(word: str) -> str:
    """'an American', 'an Estonian', but 'a Ukrainian', 'a Uruguayan'."""
    if word[:1].lower() in "aeio" or (word[:1].lower() == "u" and not word.lower().startswith(("uk", "ur"))):
        return "an"
    return "a"


DEMONYMS = {
    "Argentina": "Argentine", "Australia": "Australian", "Belarus": "Belarusian",
    "Belgium": "Belgian", "Bosnia and Herzegovina": "Bosnian", "Brazil": "Brazilian",
    "Bulgaria": "Bulgarian", "Canada": "Canadian", "Chile": "Chilean", "China": "Chinese",
    "Czech Republic": "Czech", "Czechia": "Czech", "Denmark": "Danish", "Estonia": "Estonian",
    "Finland": "Finnish", "France": "French", "Germany": "German", "Hungary": "Hungarian",
    "Israel": "Israeli", "Kazakhstan": "Kazakh", "Latvia": "Latvian", "Lithuania": "Lithuanian",
    "Mongolia": "Mongolian", "Montenegro": "Montenegrin", "Netherlands": "Dutch",
    "Norway": "Norwegian", "Poland": "Polish", "Portugal": "Portuguese", "Romania": "Romanian",
    "Russia": "Russian", "Serbia": "Serbian", "Slovakia": "Slovak", "South Africa": "South African",
    "Spain": "Spanish", "Sweden": "Swedish", "Turkey": "Turkish", "Türkiye": "Turkish",
    "Ukraine": "Ukrainian", "United Kingdom": "British", "United States": "American",
    "Uruguay": "Uruguayan",
}


# ---------------------------------------------------------------- players


@builder
def major_results_players(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    majors = ds.major_events()
    winners, _ = ds.finishers(majors, 1)
    finalists, _ = ds.finishers(majors, 2)
    titles = Counter(p for t in majors for p in ds.finishers([t], 1)[0])
    yield Prompt("major-winner-player", "Name a player who has won a Major.", "player",
                 winners, cfg.min_answers)
    yield Prompt("major-finalist-player", "Name a player who has played in a Major final.", "player",
                 finalists, cfg.min_answers)
    yield Prompt("multi-major-winner", "Name a player who has won more than one Major.", "player",
                 {p for p, n in titles.items() if n >= 2}, cfg.min_answers_small)


@builder
def major_attendance(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    attended: dict[str, set[str]] = defaultdict(set)
    for t in ds.major_events():
        for pl in ds.placements_at(t.key):
            for p in pl.players:
                attended[p].add(t.key)
    n = cfg.many_majors
    yield Prompt("major-veteran", f"Name a player who has played at {n} or more Majors.", "player",
                 {p for p, ev in attended.items() if len(ev) >= n}, cfg.min_answers_small)

    by_nation: dict[str, set[str]] = defaultdict(set)
    for p in attended:
        nation = ds.players[p].nationality
        if nation:
            by_nation[nation].add(p)
    for nation, players in sorted(by_nation.items()):
        who = f"{article(DEMONYMS[nation])} {DEMONYMS[nation]} player" if nation in DEMONYMS \
            else f"a player from {nation}"
        yield Prompt(f"major-player-{slug(nation)}", f"Name {who} who has played at a Major.",
                     "player", players, cfg.min_answers)


@builder
def young_major_winners(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    young = set()
    for t in ds.major_events():
        for pl in ds.placements_at(t.key):
            if pl.best != 1 or not t.day:
                continue
            for p in pl.players:
                born = ds.players[p].birthdate
                if born and age_on(born, t.day) < 20:
                    young.add(p)
    yield Prompt("major-winner-teen", "Name a player who won a Major before turning 20.", "player",
                 young, cfg.min_answers_small)


@builder
def big_earners(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    floor = cfg.earnings_threshold
    yield Prompt("earnings-over", f"Name a player who has won over ${floor:,} in prize money.", "player",
                 {k for k, p in ds.players.items() if p.is_player and p.earnings > floor}, cfg.min_answers)


@builder
def team_alumni(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    by_team: dict[str, set[str]] = defaultdict(set)
    for m in ds.squads:
        if m.is_player_row and (m.left is None or m.left >= cfg.era_start):
            by_team[m.team].add(m.player)
    for team, players in sorted(by_team.items()):
        yield Prompt(f"played-for-{slug(team)}", f"Name a player who has played for {ds.display('team', team)}.",
                     "player", players, cfg.min_answers)


@builder
def cs2_era_winners(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    events = [t for t in ds.events(tier="1", since=cfg.cs2_release) if not ds.is_stage(t)]
    players, teams = ds.finishers(events, 1)
    yield Prompt("s-tier-winner-player-cs2", "Name a player who has won an S-Tier event in the CS2 era.",
                 "player", players, cfg.min_answers)
    yield Prompt("s-tier-winner-team-cs2", "Name a team that has won an S-Tier event in the CS2 era.",
                 "team", teams, cfg.min_answers_small)


# ---------------------------------------------------------------- teams


@builder
def major_results_teams(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    majors = ds.major_events()
    _, winners = ds.finishers(majors, 1)
    _, finalists = ds.finishers(majors, 2)
    _, attended = ds.finishers(majors, 10**9)
    yield Prompt("major-winner-team", "Name a team that has won a Major.", "team", winners, cfg.min_answers_small)
    yield Prompt("major-finalist-team", "Name a team that has played in a Major final.", "team",
                 finalists, cfg.min_answers)
    yield Prompt("major-team", "Name a team that has played at a Major.", "team", attended, cfg.min_answers)


# ---------------------------------------------------------------- events


@builder
def major_places(ds: Dataset, cfg: Config) -> Iterator[Prompt]:
    majors = ds.major_events()
    small = cfg.min_answers_small
    yield Prompt("major-city", "Name a city that has hosted a Major.", "city",
                 {t.city for t in majors if t.city}, small)
    yield Prompt("major-country", "Name a country that has hosted a Major.", "country",
                 {t.country for t in majors if t.country}, small)
    yield Prompt("major-organizer", "Name a company that has organized a Major.", "organizer",
                 {o for t in majors for o in t.organizers}, small)
    yield Prompt("major-map", "Name a map that has been in a Major's map pool.", "map",
                 {m for t in majors for m in t.maps}, small)
    lans = [t for t in ds.events(tier="1") if t.offline and not ds.is_stage(t)]
    yield Prompt("s-tier-lan-city", "Name a city that has hosted an S-Tier LAN.", "city",
                 {t.city for t in lans if t.city}, cfg.min_answers)


def build_prompts(ds: Dataset, cfg: Config) -> list[Prompt]:
    prompts = [p for b in REGISTRY for p in b(ds, cfg)]
    ids = Counter(p.id for p in prompts)
    dupes = [i for i, n in ids.items() if n > 1]
    if dupes:
        raise ValueError(f"Duplicate prompt ids: {dupes}")
    return prompts
