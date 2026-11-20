import { describe, expect, it } from "vitest";
import type { Pack } from "../src/core/pack.ts";
import { DEFAULT_RULES, addDays, dayEnd, dayId, extendSchedule, familyOf } from "../src/core/schedule.ts";
import samplePack from "./fixtures/sample-pack.json";

const pack = samplePack as unknown as Pack;
const ids = Object.keys(pack.prompts);
const opts = { from: "2026-12-01", days: 40, seed: "test" };

describe("day boundaries", () => {
  it("uses UTC days", () => {
    expect(dayId(Date.parse("2026-11-20T23:59:59Z"))).toBe("2026-11-20");
    expect(dayId(Date.parse("2026-11-21T00:00:00Z"))).toBe("2026-11-21");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(dayEnd("2026-11-20")).toBe(Date.parse("2026-11-21T00:00:00Z"));
  });
});

describe("extendSchedule", () => {
  const s = extendSchedule(pack, {}, opts);
  const days = Object.keys(s).sort();

  it("is deterministic", () => {
    expect(extendSchedule(pack, {}, opts)).toEqual(s);
    expect(extendSchedule(pack, {}, { ...opts, seed: "other" })).not.toEqual(s);
  });

  it("gives 7 distinct, existing prompts every day", () => {
    expect(days).toHaveLength(40);
    for (const d of days) {
      expect(new Set(s[d]).size).toBe(7);
      for (const id of s[d]) expect(ids).toContain(id);
    }
  });

  it("never repeats a prompt on back-to-back days, even in a small pool", () => {
    for (let i = 1; i < days.length; i++) {
      const yesterday = new Set(s[days[i - 1]]);
      expect(s[days[i]].filter((id) => yesterday.has(id))).toEqual([]);
    }
  });

  it("never puts three prompts of one theme in a day while fresh prompts remain", () => {
    for (const d of days) {
      const fams = s[d].map((id) => familyOf(id));
      for (const f of new Set(fams)) expect(fams.filter((x) => x === f).length).toBeLessThanOrEqual(2);
    }
    expect(familyOf("major-player-denmark")).toBe("nationality");
    expect(familyOf("played-for-astralis")).toBe("alumni");
    expect(familyOf("earnings-over")).toBe("earnings-over");
    expect(DEFAULT_RULES.perDay).toBe(7);
  });

  it("never changes days before `from`, even when the pool changes", () => {
    const smaller = structuredClone(pack);
    delete smaller.prompts[s[days[10]][0]];
    const later = extendSchedule(smaller, s, { ...opts, from: days[5] });
    for (const d of days.slice(0, 5)) expect(later[d]).toEqual(s[d]);
    for (const d of Object.keys(later).filter((d) => d >= days[5])) {
      for (const id of later[d]) expect(smaller.prompts[id]).toBeDefined();
    }
  });

  it("orders each day from broad prompts to narrow ones", () => {
    const size = (id: string) => Object.keys(pack.prompts[id].answers).length;
    for (const d of days) {
      const sizes = s[d].map(size);
      expect(sizes).toEqual([...sizes].sort((a, b) => b - a));
    }
  });
});

describe("with a realistic pool", () => {
  // 120 prompts: 30 nationality, 20 alumni, 70 others with mixed types.
  const big = structuredClone(pack);
  big.prompts = {};
  const add = (id: string, type: string, n: number) => {
    big.prompts[id] = { text: id, type, answers: Object.fromEntries(Array.from({ length: n }, (_, i) => [`k${i}`, ["x", 0]])) };
  };
  for (let i = 0; i < 30; i++) add(`major-player-nation${i}`, "player", 20 + i);
  for (let i = 0; i < 20; i++) add(`played-for-team${i}`, "player", 30 + i);
  for (let i = 0; i < 70; i++) add(`misc-${i}`, ["player", "team", "city", "map", "organizer"][i % 5], 10 + i);
  const s = extendSchedule(big, {}, { from: "2027-01-01", days: 120, seed: "big" });
  const days = Object.keys(s).sort();

  it("keeps one prompt per theme per day", () => {
    for (const d of days) expect(new Set(s[d].map((id) => familyOf(id))).size).toBe(7);
  });

  it("rests every prompt for at least ten days", () => {
    const last = new Map<string, number>();
    days.forEach((d, i) => {
      for (const id of s[d]) {
        if (last.has(id)) expect(i - last.get(id)!, `${id} on ${d}`).toBeGreaterThanOrEqual(10);
        last.set(id, i);
      }
    });
  });

  it("deals every prompt within its first 30 days", () => {
    expect(new Set(days.slice(0, 30).flatMap((d) => s[d])).size).toBe(120);
  });

  it("respects the per-type caps", () => {
    for (const d of days) {
      expect(s[d].filter((id) => big.prompts[id].type === "player").length).toBeLessThanOrEqual(4);
      expect(s[d].filter((id) => big.prompts[id].type === "team").length).toBeLessThanOrEqual(2);
    }
  });
});
