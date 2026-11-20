// Build the game pack from the pipeline's output.
//   node scripts/build-pack.mjs [--from ../pipeline/data/out] [--out src/data/pack.json]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const from = resolve(args.from ?? "../pipeline/data/out");
const out = resolve(args.out ?? "src/data/pack.json");
const read = (name) => JSON.parse(readFileSync(`${from}/${name}`, "utf8"));

const prompts = read("prompts.json");
const index = read("alias_index.json");
const meta = read("meta.json");

const pack = {
  version: 1,
  built_at: meta.built_at,
  data_through: meta.data_through ?? null,
  attribution: meta.attribution,
  license_url: meta.license_url,
  tiers: meta.tiers,
  prior_strength: meta.live_prior_strength,
  prompts: Object.fromEntries(
    prompts.map((p) => [p.id, {
      text: p.text,
      type: p.type,
      answers: Object.fromEntries(p.answers.map((a) => [a.key, [a.name, a.share]])),
    }]),
  ),
  index: Object.fromEntries(Object.entries(index).map(([t, v]) => [t, v.leet])),
  names: Object.fromEntries(Object.entries(index).map(([t, v]) => [t, v.names ?? {}])),
};

for (const [type, idx] of Object.entries(pack.index)) {
  if (!Object.keys(idx).length) throw new Error(`empty alias index for type ${type}`);
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(pack));
const kb = (Buffer.byteLength(JSON.stringify(pack)) / 1024).toFixed(0);
console.log(`pack: ${Object.keys(pack.prompts).length} prompts, types ${Object.keys(pack.index).join(", ")}, ${kb} KB -> ${out}`);
