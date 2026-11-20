// Extend the daily schedule. Days before --from (default: tomorrow, or today if
// today isn't scheduled yet) are kept exactly as they are.
//   node scripts/schedule.mjs [--days 120] [--seed cs-krillion] [--from YYYY-MM-DD]
//                             [--pack src/data/pack.json] [--out src/data/schedule.json]
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { addDays, dayId, extendSchedule } from "../src/core/schedule.ts";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const packPath = args.pack ?? "src/data/pack.json";
const out = args.out ?? "src/data/schedule.json";
const pack = JSON.parse(readFileSync(packPath, "utf8"));
const existing = existsSync(out) ? JSON.parse(readFileSync(out, "utf8")) : {};
const today = dayId(Date.now());
const from = args.from ?? (existing[today] ? addDays(today, 1) : today);

const missingToday = (existing[today] ?? []).filter((id) => !pack.prompts[id]);
if (from > today && missingToday.length) {
  console.error(`Today's schedule uses prompts that are no longer in the pack: ${missingToday.join(", ")}`);
  console.error(`Re-run with --from ${today} to reschedule today (players mid-game would see new prompts).`);
  process.exit(1);
}

const schedule = extendSchedule(pack, existing, {
  from,
  days: Number(args.days ?? 120),
  seed: args.seed ?? "cs-krillion",
});
writeFileSync(out, JSON.stringify(schedule, null, 1));
const days = Object.keys(schedule).sort();
console.log(`schedule: ${days.length} days (${days[0]} .. ${days.at(-1)}), regenerated from ${from}`);
for (const d of days.filter((d) => d >= today).slice(0, 3)) console.log(`  ${d}: ${schedule[d].join(", ")}`);
