// How the page talks to the game: over HTTP to the Worker, or in-page for the
// prototype (same Game code, memory store, adjustable clock).

import type { DayInfo, GuessResult, Reveal, StartResult, Summary } from "../core/game.ts";
import { Game } from "../core/game.ts";
import type { Pack, Schedule } from "../core/pack.ts";
import type { MemoryStore } from "../core/store.ts";

export interface GameApi {
  info(): Promise<DayInfo>;
  start(round: number): Promise<StartResult>;
  guess(day: string, round: number, text: string): Promise<GuessResult>;
  reveal(day: string, round: number): Promise<Reveal>;
  summary(day: string): Promise<Summary>;
}

export class RemoteApi implements GameApi {
  private async call<T>(path: string, body?: unknown): Promise<T> {
    const res = await fetch(path, body === undefined
      ? { credentials: "same-origin" }
      : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((data as { error?: string }).error ?? `Request failed (HTTP ${res.status}).`);
    return data as T;
  }

  info() { return this.call<DayInfo>("/api/day"); }
  start(round: number) { return this.call<StartResult>("/api/start", { round }); }
  guess(day: string, round: number, text: string) { return this.call<GuessResult>("/api/guess", { day, round, text }); }
  reveal(day: string, round: number) {
    return this.call<Reveal>(`/api/reveal?day=${encodeURIComponent(day)}&round=${round}`);
  }
  summary(day: string) { return this.call<Summary>(`/api/summary?day=${encodeURIComponent(day)}`); }
}

export class LocalApi implements GameApi {
  readonly game: Game;
  readonly store: MemoryStore;
  offsetDays = 0;
  private run = "prototype-player";

  constructor(pack: Pack, schedule: Schedule, store: MemoryStore) {
    this.store = store;
    this.game = new Game(pack, schedule, store);
  }

  private now() { return Date.now() + this.offsetDays * 86_400_000; }
  async info() { return this.game.info(this.now()); }
  async start(round: number) { return this.game.start(this.run, round, this.now()); }
  async guess(day: string, round: number, text: string) { return this.game.guess(this.run, day, round, text, this.now()); }
  async reveal(day: string, round: number) { return this.game.reveal(this.run, day, round, this.now()); }
  async summary(day: string) { return this.game.summary(this.run, day, this.now()); }
}
