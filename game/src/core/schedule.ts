// Daily schedule: which 7 prompts each day, the same for everyone.
//
// Prompts are dealt least-recently-used first (ties broken by a seeded hash), so
// each prompt comes back about once per cycle through the pool. Each day takes at
// most one prompt per theme ("family") and caps how many share an answer type.
// Extending the schedule never changes days before `from`, so the day being played
// stays the same even after the pool changes; scripts/schedule.mjs starts at
// tomorrow.

import type { Pack, Schedule } from "./pack.ts";

export const RESET_HOUR_UTC = 0; // a new day starts at 00:00 UTC

export interface ScheduleRules {
  perDay: number;
  maxPerType: Record<string, number>;
  /** [family name, pattern]: prompts whose id matches the same pattern share a family */
  families: [string, RegExp][];
}

export const DEFAULT_RULES: ScheduleRules = {
  perDay: 7,
  maxPerType: { player: 4, team: 2 },
  families: [
    ["nationality", /^major-player-/],
    ["alumni", /^played-for-/],
    ["major-players", /^(major-winner-player|major-finalist-player|multi-major-winner|major-winner-teen|major-veteran)$/],
    ["major-teams", /^(major-winner-team|major-finalist-team|major-team)$/],
    ["s-tier-winners", /^s-tier-winner-/],
    ["host-places", /^(major-city|major-country|s-tier-lan-city)$/],
  ],
};

export function dayId(nowMs: number, resetHourUtc = RESET_HOUR_UTC): string {
  return new Date(nowMs - resetHourUtc * 3_600_000).toISOString().slice(0, 10);
}

export function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Millisecond timestamp when `day` ends (the next reset). */
export function dayEnd(day: string, resetHourUtc = RESET_HOUR_UTC): number {
  return Date.parse(`${addDays(day, 1)}T00:00:00Z`) + resetHourUtc * 3_600_000;
}

export function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export function familyOf(id: string, rules: ScheduleRules = DEFAULT_RULES): string {
  for (const [name, re] of rules.families) if (re.test(id)) return name;
  return id;
}

const dayNumber = (day: string) => Math.round(Date.parse(`${day}T00:00:00Z`) / 86_400_000);

export function extendSchedule(
  pack: Pack,
  existing: Schedule,
  opts: { from: string; days: number; seed: string; rules?: ScheduleRules },
): Schedule {
  const rules = opts.rules ?? DEFAULT_RULES;
  const pool = Object.keys(pack.prompts).sort();
  if (pool.length < rules.perDay) {
    throw new Error(`Need at least ${rules.perDay} prompts, the pack has ${pool.length}.`);
  }
  const out: Schedule = {};
  const lastUsed = new Map<string, number>();
  for (const day of Object.keys(existing).filter((d) => d < opts.from).sort()) {
    out[day] = existing[day];
    for (const id of existing[day]) lastUsed.set(id, dayNumber(day));
  }

  const NEVER = -1e9;
  // minimum days a prompt rests before coming back (up to a week, if the pool allows)
  const minRest = Math.min(7, Math.max(0, Math.floor(pool.length / rules.perDay) - 1));
  const typeOf = (id: string) => pack.prompts[id].type;
  const size = (id: string) => Object.keys(pack.prompts[id].answers).length;

  for (let i = 0; i < opts.days; i++) {
    const day = addDays(opts.from, i);
    const order = [...pool].sort((a, b) => {
      const la = lastUsed.get(a) ?? NEVER;
      const lb = lastUsed.get(b) ?? NEVER;
      if (la !== lb) return la - lb;
      return fnv1a(`${opts.seed}:${la}:${a}`) - fnv1a(`${opts.seed}:${lb}:${b}`) || (a < b ? -1 : 1);
    });

    // Least recently used first, one prompt per theme. If that can't fill the day
    // without bringing back a prompt played in the last `minRest` days, a theme may
    // appear twice (then more) before a prompt repeats that soon.
    const today = dayNumber(day);
    const isFresh = (id: string) => (lastUsed.get(id) ?? NEVER) < today - minRest;
    const picked: string[] = [];
    const tryPick = (freshOnly: boolean, perFamily: number, checkType: boolean) => {
      for (const id of order) {
        if (picked.length >= rules.perDay) return;
        if (picked.includes(id) || (freshOnly && !isFresh(id))) continue;
        const fam = familyOf(id, rules);
        if (picked.filter((p) => familyOf(p, rules) === fam).length >= perFamily) continue;
        const cap = rules.maxPerType[typeOf(id)];
        if (checkType && cap !== undefined && picked.filter((p) => typeOf(p) === typeOf(id)).length >= cap) continue;
        picked.push(id);
      }
    };
    tryPick(true, 1, true);
    tryPick(true, 2, true);
    tryPick(true, Infinity, true);
    tryPick(false, 1, true); // pool too small to stay fresh: repeat the least recent
    tryPick(false, Infinity, false);

    // broad prompts first, narrow ones last: a gentle difficulty ramp
    picked.sort((a, b) => size(b) - size(a) || (a < b ? -1 : 1));
    out[day] = picked;
    for (const id of picked) lastUsed.set(id, dayNumber(day));
  }
  return out;
}
