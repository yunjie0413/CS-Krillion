// Storage the game logic needs. D1 in production (src/worker/d1store.ts), memory
// in tests and in the in-browser prototype.

export interface RoundRow {
  run_id: string;
  day: string;
  round: number;
  prompt_id: string;
  started_at: number;
  answer_key: string | null;
  points: number | null;
  tier: string | null;
  finished_at: number | null;
  guesses: number;
}

export interface Store {
  getRound(run: string, day: string, round: number): Promise<RoundRow | null>;
  /** Insert the round if it doesn't exist yet; return the stored row either way. */
  startRound(run: string, day: string, round: number, promptId: string, now: number): Promise<RoundRow>;
  /** Count one more guess; returns the new total. */
  addGuess(run: string, day: string, round: number): Promise<number>;
  /** Finish an unfinished round. Returns false if it was already finished. */
  finishRound(run: string, day: string, round: number, answerKey: string | null,
    points: number, tier: string | null, now: number): Promise<boolean>;
  getRounds(run: string, day: string): Promise<RoundRow[]>;
  getCounts(promptId: string): Promise<Map<string, number>>;
  addCount(promptId: string, key: string): Promise<void>;
}

export interface MemoryDump {
  rounds: RoundRow[];
  counts: [string, [string, number][]][];
}

export class MemoryStore implements Store {
  private rounds = new Map<string, RoundRow>();
  private counts = new Map<string, Map<string, number>>();
  private id = (run: string, day: string, round: number) => `${run}|${day}|${round}`;

  /** Plain-JSON copy of everything, e.g. to survive a page reload in the prototype. */
  dump(): MemoryDump {
    return {
      rounds: [...this.rounds.values()].map((r) => ({ ...r })),
      counts: [...this.counts].map(([p, m]) => [p, [...m]]),
    };
  }

  static from(d: Partial<MemoryDump> | undefined): MemoryStore {
    const s = new MemoryStore();
    for (const r of d?.rounds ?? []) s.rounds.set(s.id(r.run_id, r.day, r.round), { ...r });
    for (const [p, entries] of d?.counts ?? []) s.counts.set(p, new Map(entries));
    return s;
  }

  async getRound(run: string, day: string, round: number) {
    const r = this.rounds.get(this.id(run, day, round));
    return r ? { ...r } : null;
  }

  async startRound(run: string, day: string, round: number, promptId: string, now: number) {
    const key = this.id(run, day, round);
    if (!this.rounds.has(key)) {
      this.rounds.set(key, {
        run_id: run, day, round, prompt_id: promptId, started_at: now,
        answer_key: null, points: null, tier: null, finished_at: null, guesses: 0,
      });
    }
    return { ...this.rounds.get(key)! };
  }

  async addGuess(run: string, day: string, round: number) {
    const r = this.rounds.get(this.id(run, day, round));
    if (!r) return 0;
    r.guesses += 1;
    return r.guesses;
  }

  async finishRound(run: string, day: string, round: number, answerKey: string | null,
    points: number, tier: string | null, now: number) {
    const r = this.rounds.get(this.id(run, day, round));
    if (!r || r.finished_at !== null) return false;
    Object.assign(r, { answer_key: answerKey, points, tier, finished_at: now });
    return true;
  }

  async getRounds(run: string, day: string) {
    return [...this.rounds.values()]
      .filter((r) => r.run_id === run && r.day === day)
      .sort((a, b) => a.round - b.round)
      .map((r) => ({ ...r }));
  }

  async getCounts(promptId: string) {
    return new Map(this.counts.get(promptId) ?? []);
  }

  async addCount(promptId: string, key: string) {
    const m = this.counts.get(promptId) ?? new Map<string, number>();
    m.set(key, (m.get(key) ?? 0) + 1);
    this.counts.set(promptId, m);
  }
}
