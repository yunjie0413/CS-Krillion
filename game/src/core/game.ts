// Game rules, independent of where they run (Worker + D1, or the browser + memory).
//
// A round's 25-second timer starts on the server the first time the player opens
// it and can't be restarted. Wrong guesses are free until time runs out (capped
// per round). A correct answer is scored from its live pick share *before* it is
// counted, so your own answer never makes itself less rare.

import { Matcher } from "./names.ts";
import type { Pack, PackPrompt, Schedule } from "./pack.ts";
import { dayEnd, dayId } from "./schedule.ts";
import { liveShare, tierFor, totalOf } from "./scoring.ts";
import type { RoundRow, Store } from "./store.ts";

export const ROUND_MS = 25_000;
export const GRACE_MS = 1_500; // allowance for network latency
export const MAX_GUESSES = 40; // per round
export const TIER_EMOJI = ["⬜", "🟨", "🟩", "🟦", "🟪", "🌟"]; // most common -> rarest
export const MISS_EMOJI = "⬛";

export class GameError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface DayInfo {
  day: string;
  rounds: number;
  round_ms: number;
  ends_at: number;
  max_points: number;
  tiers: { name: string; points: number }[];
  attribution: string;
  license_url: string;
  data_through: string | null;
}

export interface RoundResult {
  round: number;
  text: string;
  answer: { name: string; tier: string; points: number } | null;
  points: number;
}

export interface StartResult {
  day: string;
  round: number;
  text: string;
  type: string;
  deadline: number;
  now: number;
  finished: RoundResult | null;
}

export type GuessResult =
  | { status: "correct"; name: string; tier: string; points: number; share: number }
  | { status: "wrong"; name: string }
  | { status: "unknown" }
  | { status: "timeout" }
  | { status: "limit" }
  | { status: "done"; result: RoundResult };

export interface RevealAnswer { name: string; share: number; tier: string }

export interface Reveal {
  round: number;
  text: string;
  yours: RoundResult;
  common: RevealAnswer[];
  rare: RevealAnswer[];
  answer_count: number;
}

export interface Summary {
  day: string;
  total: number;
  max: number;
  complete: boolean;
  rounds: (RoundResult | null)[];
  share_text: string;
}

export class Game {
  readonly pack: Pack;
  readonly schedule: Schedule;
  readonly store: Store;
  private matchers = new Map<string, Matcher>();

  constructor(pack: Pack, schedule: Schedule, store: Store) {
    this.pack = pack;
    this.schedule = schedule;
    this.store = store;
  }

  info(now: number): DayInfo {
    const day = dayId(now);
    const top = this.pack.tiers[this.pack.tiers.length - 1].points;
    return {
      day,
      rounds: this.idsFor(day).length,
      round_ms: ROUND_MS,
      ends_at: dayEnd(day),
      max_points: top * this.idsFor(day).length,
      tiers: this.pack.tiers.map((t) => ({ name: t.name, points: t.points })),
      attribution: this.pack.attribution,
      license_url: this.pack.license_url,
      data_through: this.pack.data_through,
    };
  }

  async start(run: string, round: number, now: number): Promise<StartResult> {
    const day = dayId(now);
    const id = this.promptId(day, round);
    let row = (await this.store.getRound(run, day, round)) ?? (await this.store.startRound(run, day, round, id, now));
    row = await this.expireIfLate(row, now);
    const p = this.prompt(row.prompt_id);
    return {
      day, round, text: p.text, type: p.type, deadline: row.started_at + ROUND_MS, now,
      finished: row.finished_at !== null ? this.result(row) : null,
    };
  }

  async guess(run: string, day: string, round: number, text: string, now: number): Promise<GuessResult> {
    let row = await this.store.getRound(run, day, round);
    if (!row) throw new GameError(409, "Start the round first.");
    if (row.finished_at !== null) return { status: "done", result: this.result(row) };
    row = await this.expireIfLate(row, now);
    if (row.finished_at !== null) return { status: "timeout" };
    if ((await this.store.addGuess(run, day, round)) > MAX_GUESSES) return { status: "limit" };

    const p = this.prompt(row.prompt_id);
    const answers = new Set(Object.keys(p.answers));
    const verdict = this.matcher(p.type).judge(text, answers, (k) => p.answers[k]?.[1] ?? 0);
    if (verdict.status === "unknown") return { status: "unknown" };
    if (verdict.status === "wrong") return { status: "wrong", name: this.nameOf(p.type, verdict.key) };

    const counts = await this.store.getCounts(row.prompt_id);
    const [name, prior] = p.answers[verdict.key];
    const share = liveShare(prior, counts.get(verdict.key) ?? 0, totalOf(counts, answers), this.pack.prior_strength);
    const tier = tierFor(share, this.pack.tiers);
    if (!(await this.store.finishRound(run, day, round, verdict.key, tier.points, tier.name, now))) {
      const again = await this.store.getRound(run, day, round);
      return { status: "done", result: this.result(again!) };
    }
    await this.store.addCount(row.prompt_id, verdict.key);
    return { status: "correct", name, tier: tier.name, points: tier.points, share: round4(share) };
  }

  async reveal(run: string, day: string, round: number, now: number): Promise<Reveal> {
    let row = await this.store.getRound(run, day, round);
    if (!row) throw new GameError(409, "Start the round first.");
    row = await this.expireIfLate(row, now);
    if (row.finished_at === null) throw new GameError(409, "The round is still running.");
    const p = this.prompt(row.prompt_id);
    const keys = Object.keys(p.answers);
    const counts = await this.store.getCounts(row.prompt_id);
    const total = totalOf(counts, keys);
    const ranked = keys
      .map((k) => {
        const share = liveShare(p.answers[k][1], counts.get(k) ?? 0, total, this.pack.prior_strength);
        return { name: p.answers[k][0], share: round4(share), tier: tierFor(share, this.pack.tiers).name };
      })
      .sort((a, b) => b.share - a.share || (a.name < b.name ? -1 : 1));
    return {
      round, text: p.text, yours: this.result(row), answer_count: keys.length,
      common: ranked.slice(0, 5),
      rare: ranked.length > 5 ? ranked.slice(-3).reverse() : [],
    };
  }

  async summary(run: string, day: string, now: number): Promise<Summary> {
    const ids = this.idsFor(day);
    const byRound = new Map<number, RoundRow>();
    for (const r of await this.store.getRounds(run, day)) byRound.set(r.round, await this.expireIfLate(r, now));
    const rounds = ids.map((_, i) => {
      const r = byRound.get(i + 1);
      return r && r.finished_at !== null ? this.result(r) : null;
    });
    const total = rounds.reduce((s, r) => s + (r?.points ?? 0), 0);
    const max = this.pack.tiers[this.pack.tiers.length - 1].points * ids.length;
    const tierIndex = new Map(this.pack.tiers.map((t, i) => [t.name, i]));
    const squares = rounds
      .map((r) => (r?.answer ? TIER_EMOJI[tierIndex.get(r.answer.tier) ?? 0] ?? "🟫" : MISS_EMOJI))
      .join("");
    return {
      day, total, max, rounds,
      complete: rounds.every((r) => r !== null),
      share_text: `CS-Krillion ${day} · ${total}/${max}\n${squares}`,
    };
  }

  // ---- helpers ----------------------------------------------------------

  private idsFor(day: string): string[] {
    const ids = this.schedule[day];
    if (!ids?.length) throw new GameError(503, `No prompts scheduled for ${day}.`);
    return ids;
  }

  private promptId(day: string, round: number): string {
    const ids = this.idsFor(day);
    if (!Number.isInteger(round) || round < 1 || round > ids.length) {
      throw new GameError(400, `Round must be 1-${ids.length}.`);
    }
    return ids[round - 1];
  }

  private prompt(id: string): PackPrompt {
    const p = this.pack.prompts[id];
    if (!p) throw new GameError(500, `Prompt ${id} is missing from the pack.`);
    return p;
  }

  private matcher(type: string): Matcher {
    let m = this.matchers.get(type);
    if (!m) {
      m = new Matcher(this.pack.index[type] ?? {});
      this.matchers.set(type, m);
    }
    return m;
  }

  private nameOf(type: string, key: string): string {
    return this.pack.names[type]?.[key] ?? key.replace(/_/g, " ");
  }

  private async expireIfLate(row: RoundRow, now: number): Promise<RoundRow> {
    if (row.finished_at !== null || now <= row.started_at + ROUND_MS + GRACE_MS) return row;
    await this.store.finishRound(row.run_id, row.day, row.round, null, 0, null, row.started_at + ROUND_MS);
    return (await this.store.getRound(row.run_id, row.day, row.round)) ?? row;
  }

  private result(row: RoundRow): RoundResult {
    const p = this.prompt(row.prompt_id);
    const a = row.answer_key ? p.answers[row.answer_key] : undefined;
    return {
      round: row.round,
      text: p.text,
      answer: a ? { name: a[0], tier: row.tier ?? "", points: row.points ?? 0 } : null,
      points: row.points ?? 0,
    };
  }
}

const round4 = (x: number) => Math.round(x * 1e4) / 1e4;
