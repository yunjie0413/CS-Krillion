"""Name normalisation, alias generation and answer matching.

The game's runtime matcher should apply the same rules so build-time checks
and live play agree. To port to JS:

  norm(s):  NFKD -> drop combining marks -> casefold -> map ø/æ/œ/ł/đ/ð/þ/ı
            -> "&" to "and" -> keep only [a-z0-9]
  leet(n):  0->o 1->i 3->e 4->a 5->s 7->t    (applied to norm output)

Lookup: every entity whose alias has the same leet key (this includes exact
matches), else (optional) a fuzzy search over leet keys that must land on
exactly one entity. When several candidates match, the judge prefers one that
is a valid answer for the prompt.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_SPECIAL = str.maketrans({
    "ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i",
})
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
TEAM_AFFIXES = frozenset({"team", "esports", "esport", "gaming", "clan", "club", "gg"})
_DISAMBIG = re.compile(r"\s*\([^)]*\)\s*$")  # "Hobbit (Kazakh player)" -> "Hobbit"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold().translate(_SPECIAL).replace("&", "and")
    return re.sub(r"[^0-9a-z]+", "", s)


def leet(n: str) -> str:
    return n.translate(LEET)


def strip_disambiguation(name: str) -> str:
    return _DISAMBIG.sub("", name).strip()


def page_to_label(key: str) -> str:
    return strip_disambiguation(key.replace("_", " "))


def team_name_variants(name: str) -> set[str]:
    """'Team Vitality' -> {'Team Vitality', 'Vitality'}; 'FaZe Clan' -> {.., 'FaZe'}."""
    out = {name}
    words = name.split()
    core = [w for w in words if norm(w) not in TEAM_AFFIXES]
    if core and len(core) < len(words):
        out.add(" ".join(core))
    return out


def max_edits(length: int) -> int:
    if length <= 3:
        return 0
    if length <= 7:
        return 1
    return 2


def osa_distance(a: str, b: str, cutoff: int) -> int:
    """Optimal-string-alignment distance (Levenshtein + adjacent swaps).

    Returns cutoff + 1 as soon as the distance must exceed `cutoff`.
    """
    if abs(len(a) - len(b)) > cutoff:
        return cutoff + 1
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if (prev2 is not None and i > 1 and j > 1
                    and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]):
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > cutoff:
            return cutoff + 1
        prev2, prev = prev, cur
    return prev[-1]


@dataclass(frozen=True)
class Verdict:
    status: str           # "correct" | "wrong" | "unknown"
    key: str | None       # entity the input resolved to
    how: str = ""         # "exact" | "leet" | "fuzzy"


class Matcher:
    """Resolves free text to entity keys of one type (players, teams, ...)."""

    def __init__(self, exact: Mapping[str, Iterable[str]], leet_keys: Mapping[str, Iterable[str]],
                 *, fuzzy: bool = True) -> None:
        self.exact = {k: frozenset(v) for k, v in exact.items()}
        self.leet = {k: frozenset(v) for k, v in leet_keys.items()}
        self.fuzzy = fuzzy
        self._by_len: dict[int, list[str]] = defaultdict(list)
        for k in self.leet:
            self._by_len[len(k)].append(k)

    @classmethod
    def from_universe(cls, universe: Mapping[str, Iterable[str]], *, fuzzy: bool = True) -> "Matcher":
        exact, leet_keys = build_index(universe)
        return cls(exact, leet_keys, fuzzy=fuzzy)

    def lookup(self, text: str) -> tuple[frozenset[str], str]:
        n = norm(text)
        if len(n) < 2:
            return frozenset(), ""
        f = leet(n)
        # Pool exact and leet hits (exact ones are a subset): someone typing "device"
        # may mean dev1ce, so judge() can pick whichever candidate is a valid answer.
        if f in self.leet:
            return self.leet[f], "exact" if n in self.exact else "leet"
        if not self.fuzzy:
            return frozenset(), ""
        limit = max_edits(len(f))
        if limit == 0:
            return frozenset(), ""
        best, hits = limit + 1, set()
        for length in range(len(f) - limit, len(f) + limit + 1):
            for k in self._by_len.get(length, ()):
                d = osa_distance(f, k, min(best, limit))
                if d < best:
                    best, hits = d, set(self.leet[k])
                elif d == best:
                    hits |= self.leet[k]
        if best <= limit and len(hits) == 1:  # a typo must point at exactly one entity
            return frozenset(hits), "fuzzy"
        return frozenset(), ""

    def judge(self, text: str, answers: set[str] | frozenset[str],
              rank: Mapping[str, float] | None = None) -> Verdict:
        """`rank` breaks ties when a name is shared by several valid answers."""
        candidates, how = self.lookup(text)
        if not candidates:
            return Verdict("unknown", None)
        inside = [k for k in candidates if k in answers]
        if inside:
            inside.sort(key=lambda k: (-(rank or {}).get(k, 0.0), k))
            return Verdict("correct", inside[0], how)
        return Verdict("wrong", sorted(candidates)[0], how)


def build_index(universe: Mapping[str, Iterable[str]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """norm(alias) -> keys and leet(norm(alias)) -> keys."""
    exact: dict[str, set[str]] = defaultdict(set)
    leet_keys: dict[str, set[str]] = defaultdict(set)
    for key, aliases in universe.items():
        for alias in aliases:
            n = norm(alias)
            if len(n) < 2:
                continue
            exact[n].add(key)
            leet_keys[leet(n)].add(key)
    return dict(exact), dict(leet_keys)
