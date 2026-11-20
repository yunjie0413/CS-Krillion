// The game pack: everything the game needs from the data pipeline, in one JSON
// file built by scripts/build-pack.mjs from pipeline/data/out.

export interface Tier { name: string; points: number; min_share: number }

export interface PackPrompt {
  text: string;
  type: string;
  /** entity key -> [display name, prior pick share] */
  answers: Record<string, [string, number]>;
}

export interface Pack {
  version: 1;
  built_at: string;
  data_through: string | null;
  attribution: string;
  license_url: string;
  tiers: Tier[];          // most common first; last has min_share 0
  prior_strength: number; // live-blend pseudo-count S
  prompts: Record<string, PackPrompt>;
  /** per answer type: leet key -> entity keys */
  index: Record<string, Record<string, string[]>>;
  /** per answer type: entity key -> display name (for "real but wrong" replies) */
  names: Record<string, Record<string, string>>;
}

/** day ("YYYY-MM-DD", UTC after the reset hour) -> prompt ids in play order */
export type Schedule = Record<string, string[]>;
