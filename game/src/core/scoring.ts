// Rarity scoring, mirroring pipeline/cskrill/rarity.py.
//
// Live share with Dirichlet smoothing (S = pack.prior_strength):
//   q_e = (n_e + S * p_e) / (N + S)
// where p_e is the pipeline's prior share and n_e the number of earlier players who
// gave answer e (N in total). The tier is the first, most common first, whose
// min_share is <= q_e.

import type { Tier } from "./pack.ts";

export function liveShare(prior: number, count: number, totalCount: number, strength: number): number {
  return (count + strength * prior) / (totalCount + strength);
}

export function tierFor(share: number, tiers: readonly Tier[]): Tier {
  for (const t of tiers) if (share >= t.min_share) return t;
  return tiers[tiers.length - 1];
}

export function totalOf(counts: ReadonlyMap<string, number>, keys: Iterable<string>): number {
  let n = 0;
  for (const k of keys) n += counts.get(k) ?? 0;
  return n;
}
