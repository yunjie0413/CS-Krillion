import { describe, expect, it } from "vitest";
import { Matcher, leet, maxEdits, norm, osaDistance } from "../src/core/names.ts";
import type { Pack } from "../src/core/pack.ts";
import parity from "./fixtures/parity.json";
import samplePack from "./fixtures/sample-pack.json";

const pack = samplePack as unknown as Pack;

describe("parity with pipeline/cskrill/names.py", () => {
  it("normalises exactly like Python", () => {
    for (const [s, want] of Object.entries(parity.norm)) expect(norm(s), JSON.stringify(s)).toBe(want);
  });

  it("leet-folds exactly like Python", () => {
    for (const [s, want] of Object.entries(parity.leet)) expect(leet(norm(s)), JSON.stringify(s)).toBe(want);
  });

  it("looks names up exactly like Python, fuzzy matches included", () => {
    let checked = 0;
    for (const [type, queries] of Object.entries(parity.lookup)) {
      const m = new Matcher(pack.index[type]);
      for (const [q, want] of Object.entries(queries as Record<string, { keys: string[]; fuzzy: boolean }>)) {
        const got = m.lookup(q);
        expect({ keys: [...got.keys].sort(), fuzzy: got.how === "fuzzy" }, `${type}: ${q}`).toEqual(want);
        checked++;
      }
    }
    expect(checked).toBeGreaterThan(60);
  });
});

describe("matcher", () => {
  it("measures edit distance with adjacent swaps and stops early", () => {
    expect(osaDistance("zywoo", "zywo", 2)).toBe(1);
    expect(osaDistance("dveice", "device", 2)).toBe(1);
    expect(osaDistance("abcdef", "uvwxyz", 2)).toBe(3);
    expect([3, 5, 9].map(maxEdits)).toEqual([0, 1, 2]);
  });

  it("judges correct, real-but-wrong and unknown answers", () => {
    const m = new Matcher(pack.index.player);
    const winners = new Set(Object.keys(pack.prompts["major-winner-player"].answers));
    expect(m.judge("simple", winners)).toEqual({ status: "correct", key: "S1mple", how: "match" });
    expect(m.judge("NiKo", winners)).toMatchObject({ status: "wrong", key: "NiKo" });
    expect(m.judge("qwertyuiop", winners)).toEqual({ status: "unknown" });
    expect(m.judge("karigan", winners)).toEqual({ status: "correct", key: "Karrigan", how: "fuzzy" });
  });

  it("prefers the valid candidate, then the best-known one, when a name is shared", () => {
    const m = new Matcher({ device: ["Dev1ce", "Device_(Swedish_player)"] });
    expect(m.judge("device", new Set(["Dev1ce"]))).toMatchObject({ status: "correct", key: "Dev1ce" });
    const both = new Set(["Dev1ce", "Device_(Swedish_player)"]);
    const rank = (k: string) => (k === "Dev1ce" ? 0.2 : 0.01);
    expect(m.judge("device", both, rank)).toMatchObject({ key: "Dev1ce" });
  });
});
