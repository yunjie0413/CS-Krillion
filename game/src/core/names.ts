// Answer matching. Must behave exactly like pipeline/cskrill/names.py:
// test/parity.test.ts checks this against vectors generated from the Python code.
//
//   norm(s): NFKD, drop combining marks, lower-case, map ø/æ/œ/ł/đ/ð/þ/ı/ß,
//            "&" -> "and", keep only [a-z0-9]
//   leet(n): 0->o 1->i 3->e 4->a 5->s 7->t
//
// Lookup: every entity whose alias has the same leet key, else (optionally) a
// fuzzy search over leet keys that must land on exactly one entity.

const SPECIAL: Record<string, string> = {
  "ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i", "ß": "ss",
};
const LEET: Record<string, string> = { "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t" };

export function norm(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[øæœłđðþıß]/g, (c) => SPECIAL[c] ?? c)
    .replace(/&/g, "and")
    .replace(/[^0-9a-z]+/g, "");
}

export function leet(n: string): string {
  return n.replace(/[013457]/g, (c) => LEET[c] ?? c);
}

export function maxEdits(length: number): number {
  if (length <= 3) return 0;
  if (length <= 7) return 1;
  return 2;
}

/** Optimal-string-alignment distance; returns cutoff + 1 once it must exceed cutoff. */
export function osaDistance(a: string, b: string, cutoff: number): number {
  if (Math.abs(a.length - b.length) > cutoff) return cutoff + 1;
  let prev2: number[] | null = null;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i, ...new Array<number>(b.length).fill(0)];
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
      }
    }
    if (Math.min(...cur) > cutoff) return cutoff + 1;
    prev2 = prev;
    prev = cur;
  }
  return prev[b.length];
}

export type How = "match" | "fuzzy";
export interface Lookup { keys: string[]; how: How | null }
export type Verdict =
  | { status: "correct"; key: string; how: How }
  | { status: "wrong"; key: string; how: How }
  | { status: "unknown" };

/** Resolves free text to entity keys of one type, from a leet-key index. */
export class Matcher {
  readonly index: Record<string, string[]>;
  readonly fuzzy: boolean;
  private byLength = new Map<number, string[]>();

  constructor(index: Record<string, string[]>, fuzzy = true) {
    this.index = index;
    this.fuzzy = fuzzy;
    for (const k of Object.keys(index)) {
      const bucket = this.byLength.get(k.length);
      if (bucket) bucket.push(k);
      else this.byLength.set(k.length, [k]);
    }
  }

  lookup(text: string): Lookup {
    const n = norm(text);
    if (n.length < 2) return { keys: [], how: null };
    const f = leet(n);
    const hit = this.index[f];
    if (hit) return { keys: [...hit], how: "match" };
    if (!this.fuzzy) return { keys: [], how: null };
    const limit = maxEdits(f.length);
    if (limit === 0) return { keys: [], how: null };
    let best = limit + 1;
    let hits = new Set<string>();
    for (let len = f.length - limit; len <= f.length + limit; len++) {
      for (const k of this.byLength.get(len) ?? []) {
        const d = osaDistance(f, k, Math.min(best, limit));
        if (d < best) {
          best = d;
          hits = new Set(this.index[k]);
        } else if (d === best) {
          for (const key of this.index[k]) hits.add(key);
        }
      }
    }
    // a typo must point at exactly one entity
    if (best <= limit && hits.size === 1) return { keys: [...hits], how: "fuzzy" };
    return { keys: [], how: null };
  }

  /** `rank` breaks ties when a name fits several valid answers (best-known wins). */
  judge(text: string, answers: ReadonlySet<string>, rank?: (key: string) => number): Verdict {
    const { keys, how } = this.lookup(text);
    if (!keys.length || !how) return { status: "unknown" };
    const inside = keys.filter((k) => answers.has(k));
    if (inside.length) {
      inside.sort((a, b) => (rank ? rank(b) - rank(a) : 0) || (a < b ? -1 : a > b ? 1 : 0));
      return { status: "correct", key: inside[0], how };
    }
    return { status: "wrong", key: [...keys].sort()[0], how };
  }
}
