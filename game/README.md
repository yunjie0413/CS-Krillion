# CS-Krillion game

A Cloudflare Worker with a D1 database. The page is static (`public/`), and the
API checks every answer on the server, so the answer lists never reach the
browser.

## Run it locally

```bash
cd game
npm install
npm run build        # public/ (the site) and dist/prototype.html (offline prototype)
npm run db:local     # create the D1 tables locally
npx wrangler dev     # http://localhost:8787
npm test             # 25 tests, including parity with the Python matcher
```

`dist/prototype.html` is one self-contained file that runs the whole game in
the browser on the sample data, with buttons to move between days.

## Data

`src/data/pack.json` and `src/data/schedule.json` hold the sample data for now.
To switch to real data:

```bash
# in pipeline/
cskrill fetch && cskrill build
# in game/
npm run pack         # ../pipeline/data/out -> src/data/pack.json
npm run schedule     # extends the schedule starting tomorrow; past days and today never change
```

## Deploy

```bash
npx wrangler login
npx wrangler d1 create cs-krillion          # copy the printed id into wrangler.toml
npx wrangler d1 execute cs-krillion --remote --file schema.sql
npm run deploy
```

## How it works

- **Days.** Everyone gets the same 7 prompts each day, from
  `src/data/schedule.json`. A new day starts at 00:00 UTC. The schedule puts
  least recently used prompts first, gives each day at most one prompt per theme
  (one nationality prompt, one "played for" prompt, and so on), caps answer
  types, and never repeats a prompt within a week when the pool is big enough.
- **Timer.** A round's 25 seconds start on the server the first time the player
  opens it, and can't be restarted. Guesses after the deadline are refused,
  allowing 1.5 s for latency. Wrong guesses are free, up to 40 per round.
- **Matching.** This is the pipeline's matching (accents, case, leetspeak,
  small typos), ported to TypeScript. `test/names.test.ts` checks it against
  vectors generated from the Python code.
- **Scoring.** An answer's share is (n + S·p) / (N + S). Here p is the
  pipeline's estimate, n is how many earlier players gave that answer, N is all
  answers to the prompt, and S = 200. The answer is scored before it is counted.
  The share's tier sets the points: Silver 10, Gold Nova 25, Master Guardian 40,
  Legendary Eagle 60, Supreme 80, Global Elite 100.
- **Players** are anonymous: a random id in an HttpOnly cookie.

## API

| | |
|---|---|
| `GET /api/day` | today's date, round count, tiers, attribution (no prompt text) |
| `POST /api/start {round}` | opens a round, starts its timer, returns the prompt |
| `POST /api/guess {day, round, text}` | `correct` (name, tier, points, share), `wrong` (a real name that doesn't fit), `unknown`, `timeout`, `limit` or `done` |
| `GET /api/reveal?day=&round=` | most picked and rarest answers, only once the round is over |
| `GET /api/summary?day=` | per-round results, total, share text |

The code sits in `src/core` (rules, matching, schedule; runs anywhere),
`src/worker` (HTTP and D1) and `src/web` (the page).
