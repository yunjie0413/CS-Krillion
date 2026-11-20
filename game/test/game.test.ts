import { beforeEach, describe, expect, it } from "vitest";
import { GRACE_MS, Game, GameError, MAX_GUESSES, ROUND_MS } from "../src/core/game.ts";
import type { Pack } from "../src/core/pack.ts";
import { extendSchedule } from "../src/core/schedule.ts";
import { MemoryStore } from "../src/core/store.ts";
import samplePack from "./fixtures/sample-pack.json";

const pack = samplePack as unknown as Pack;
const DAY = "2026-12-01";
const T0 = Date.parse(`${DAY}T12:00:00Z`);
const schedule = { ...extendSchedule(pack, {}, { from: DAY, days: 3, seed: "t" }) };
// Make round 1 a prompt with known answers.
schedule[DAY] = ["major-winner-player", ...schedule[DAY].filter((id) => id !== "major-winner-player").slice(0, 6)];

let store: MemoryStore;
let game: Game;
beforeEach(() => {
  store = new MemoryStore();
  game = new Game(pack, schedule, store);
});

describe("a round", () => {
  it("reveals the prompt only when started, and the timer can't be restarted", async () => {
    const info = game.info(T0);
    expect(info).toMatchObject({ day: DAY, rounds: 7, round_ms: ROUND_MS, max_points: 700 });
    expect(JSON.stringify(info)).not.toContain("Major");
    const a = await game.start("p1", 1, T0);
    expect(a).toMatchObject({ text: "Name a player who has won a Major.", type: "player", deadline: T0 + ROUND_MS });
    const b = await game.start("p1", 1, T0 + 10_000);
    expect(b.deadline).toBe(T0 + ROUND_MS);
  });

  it("scores a correct answer, then refuses more guesses", async () => {
    await game.start("p1", 1, T0);
    expect(await game.guess("p1", DAY, 1, "NiKo", T0 + 1000)).toEqual({ status: "wrong", name: "NiKo" });
    expect(await game.guess("p1", DAY, 1, "asdfgh", T0 + 2000)).toEqual({ status: "unknown" });
    const r = await game.guess("p1", DAY, 1, "s1mple", T0 + 3000);
    expect(r).toMatchObject({ status: "correct", name: "s1mple" });
    expect(await game.guess("p1", DAY, 1, "dev1ce", T0 + 4000)).toMatchObject({ status: "done" });
    expect((await store.getCounts("major-winner-player")).get("S1mple")).toBe(1);
  });

  it("times out on the server, whatever the client says", async () => {
    await game.start("p1", 1, T0);
    expect(await game.guess("p1", DAY, 1, "s1mple", T0 + ROUND_MS + GRACE_MS + 1)).toEqual({ status: "timeout" });
    expect(await game.guess("p1", DAY, 1, "s1mple", T0 + ROUND_MS + 60_000)).toMatchObject({
      status: "done", result: { answer: null, points: 0 },
    });
    // a guess just inside the grace window still counts
    await game.start("p2", 1, T0);
    expect(await game.guess("p2", DAY, 1, "s1mple", T0 + ROUND_MS + GRACE_MS)).toMatchObject({ status: "correct" });
  });

  it("caps guesses per round", async () => {
    await game.start("p1", 1, T0);
    for (let i = 0; i < MAX_GUESSES; i++) await game.guess("p1", DAY, 1, "zzzz", T0 + 100);
    expect(await game.guess("p1", DAY, 1, "s1mple", T0 + 200)).toEqual({ status: "limit" });
  });

  it("rejects guesses before start and out-of-range rounds", async () => {
    await expect(game.guess("p1", DAY, 2, "x", T0)).rejects.toBeInstanceOf(GameError);
    await expect(game.start("p1", 8, T0)).rejects.toMatchObject({ status: 400 });
  });
});

describe("rarity from live play", () => {
  it("makes an answer less rare as more players give it, never counting your own", async () => {
    const first = await (async () => {
      await game.start("a", 1, T0);
      return game.guess("a", DAY, 1, "jame", T0 + 1000);
    })();
    let last = first;
    for (let i = 0; i < 300; i++) {
      await game.start(`p${i}`, 1, T0);
      last = await game.guess(`p${i}`, DAY, 1, "jame", T0 + 1000);
    }
    if (first.status !== "correct" || last.status !== "correct") throw new Error("expected correct answers");
    expect(last.share).toBeGreaterThan(first.share);
    expect(last.points).toBeLessThanOrEqual(first.points);
  });
});

describe("reveal and summary", () => {
  it("hides answers until the round is over", async () => {
    await game.start("p1", 1, T0);
    await expect(game.reveal("p1", DAY, 1, T0 + 1000)).rejects.toMatchObject({ status: 409 });
    await game.guess("p1", DAY, 1, "dev1ce", T0 + 2000);
    const r = await game.reveal("p1", DAY, 1, T0 + 3000);
    expect(r.common).toHaveLength(5);
    expect(r.rare.length).toBeGreaterThan(0);
    expect(r.yours.answer?.name).toBe("dev1ce");
    const shares = r.common.map((a) => a.share);
    expect(shares).toEqual([...shares].sort((a, b) => b - a));
  });

  it("totals the day and builds share text, counting expired rounds as misses", async () => {
    await game.start("p1", 1, T0);
    await game.guess("p1", DAY, 1, "s1mple", T0 + 1000);
    await game.start("p1", 2, T0 + 2000); // never answered: expires
    const s = await game.summary("p1", DAY, T0 + 120_000);
    expect(s.rounds[0]?.answer?.name).toBe("s1mple");
    expect(s.rounds[1]).toMatchObject({ answer: null, points: 0 });
    expect(s.rounds.slice(2).every((r) => r === null)).toBe(true);
    expect(s.complete).toBe(false);
    expect(s.share_text).toMatch(new RegExp(`^CS-Krillion ${DAY} · \\d+/700\\n.⬛`, "u"));
  });
});
