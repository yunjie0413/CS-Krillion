"""Rarity: from "how well known is this answer" to expected pick share to tier.

Before anyone plays, we estimate how often each valid answer would be picked:

    familiarity f_e   players/teams: log(1 + prize earnings) + w * log(1 + recent S-Tier top-4s)
                      cities/countries/organizers/maps: log(1 + number of S-Tier events)
    prior share p_e   proportional to exp(T * f_e)       (T = rarity.temperature)

For players that is a power law: p_e ~ (1 + earnings)^T * (1 + recent top-4s)^(T*w),
so with T = 2 an answer with twice the prize money is expected to be picked about
four times as often. (Standardising f within each set was tried first and rejected:
when most answers tie, one slightly better-known answer got almost all the share.)

Once real answers arrive, blend them in with Dirichlet smoothing, where the prior
counts as S pseudo-answers (S = rarity.live_prior_strength):

    q_e = (n_e + S * p_e) / (N + S)

With no plays q = p; as N grows, q tends to the observed pick rates. The tier of an
answer is the first tier (most common first) whose min_share is <= its share.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from .config import Config, Tier
from .model import Dataset


def familiarity(etype: str, keys: Iterable[str], ds: Dataset, cfg: Config) -> dict[str, float]:
    w = cfg.recent_weight
    if etype == "player":
        return {k: math.log1p(ds.players[k].earnings) + w * math.log1p(ds.recent_top4["player"][k])
                for k in keys}
    if etype == "team":
        return {k: math.log1p(ds.teams[k].earnings if k in ds.teams else 0)
                + w * math.log1p(ds.recent_top4["team"][k]) for k in keys}
    counts = ds.label_counts.get(etype, {})
    return {k: math.log1p(counts.get(k, 0)) for k in keys}


def prior_shares(fam: Mapping[str, float], temperature: float) -> dict[str, float]:
    if not fam:
        return {}
    top = max(fam.values())  # subtract the max so exp() cannot overflow
    weights = {k: math.exp(temperature * (f - top)) for k, f in sorted(fam.items())}
    total = sum(weights.values())
    return {k: w / total for k, w in weights.items()}


def blend(prior: Mapping[str, float], counts: Mapping[str, int], strength: float) -> dict[str, float]:
    n = sum(counts.get(k, 0) for k in prior)
    return {k: (counts.get(k, 0) + strength * p) / (n + strength) for k, p in prior.items()}


def tier_for(share: float, tiers: tuple[Tier, ...]) -> Tier:
    for tier in tiers:  # sorted from most common (highest min_share) to rarest
        if share >= tier.min_share:
            return tier
    return tiers[-1]
