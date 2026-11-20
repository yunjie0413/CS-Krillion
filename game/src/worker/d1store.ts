import type { RoundRow, Store } from "../core/store.ts";

export class D1Store implements Store {
  private db: D1Database;

  constructor(db: D1Database) {
    this.db = db;
  }

  async getRound(run: string, day: string, round: number) {
    return this.db
      .prepare("SELECT * FROM rounds WHERE run_id = ? AND day = ? AND round = ?")
      .bind(run, day, round)
      .first<RoundRow>();
  }

  async startRound(run: string, day: string, round: number, promptId: string, now: number) {
    await this.db
      .prepare(`INSERT INTO rounds (run_id, day, round, prompt_id, started_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (run_id, day, round) DO NOTHING`)
      .bind(run, day, round, promptId, now)
      .run();
    return (await this.getRound(run, day, round))!;
  }

  async addGuess(run: string, day: string, round: number) {
    const row = await this.db
      .prepare("UPDATE rounds SET guesses = guesses + 1 WHERE run_id = ? AND day = ? AND round = ? RETURNING guesses")
      .bind(run, day, round)
      .first<{ guesses: number }>();
    return row?.guesses ?? 0;
  }

  async finishRound(run: string, day: string, round: number, answerKey: string | null,
    points: number, tier: string | null, now: number) {
    const res = await this.db
      .prepare(`UPDATE rounds SET answer_key = ?, points = ?, tier = ?, finished_at = ?
                WHERE run_id = ? AND day = ? AND round = ? AND finished_at IS NULL`)
      .bind(answerKey, points, tier, now, run, day, round)
      .run();
    return (res.meta.changes ?? 0) > 0;
  }

  async getRounds(run: string, day: string) {
    const { results } = await this.db
      .prepare("SELECT * FROM rounds WHERE run_id = ? AND day = ? ORDER BY round")
      .bind(run, day)
      .all<RoundRow>();
    return results;
  }

  async getCounts(promptId: string) {
    const { results } = await this.db
      .prepare("SELECT entity_key, n FROM answer_counts WHERE prompt_id = ?")
      .bind(promptId)
      .all<{ entity_key: string; n: number }>();
    return new Map(results.map((r) => [r.entity_key, r.n]));
  }

  async addCount(promptId: string, key: string) {
    await this.db
      .prepare(`INSERT INTO answer_counts (prompt_id, entity_key, n) VALUES (?, ?, 1)
                ON CONFLICT (prompt_id, entity_key) DO UPDATE SET n = n + 1`)
      .bind(promptId, key)
      .run();
  }
}
