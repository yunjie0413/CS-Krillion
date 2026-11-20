# CS-Krillion data pipeline

Builds the prompts and answer lists for a CS2 trivia game in the style of
Krillion ("Name a player who has won a Major"; rarer correct answers score
more) from Liquipedia's LiquipediaDB (LPDB) API.

It is an offline batch job. It fetches once, caches everything, and writes
static JSON. The game serves those files and never calls Liquipedia itself.

## Before your first fetch

1. **Request API access** at <https://liquipedia.net/api>. Free access is only
   for educational, non-commercial or community projects, and **those projects
   must be open source**. Access is usually time-limited. Your key shows up in
   the LiquipediaDB Dashboard.
2. **Publish this repo** publicly. It is MIT-licensed already.
3. **Set your User-Agent** to your repo URL and email. Liquipedia blocks
   generic agents, so the fetcher won't run until you do. To keep the email out
   of the public repo, set `LIQUIPEDIA_USER_AGENT` in your environment instead
   of editing `user_agent` in `config.yaml`.

## Quick start

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cskrill demo        # builds from bundled sample data, no key needed
pytest              # 34 tests

export LIQUIPEDIA_API_KEY=...      # never commit it
export LIQUIPEDIA_USER_AGENT="CS2Krillion-data/0.1 (https://github.com/yunjie0413/CS-Krillion; you@example.com)"
cskrill fetch       # about 50 to 90 API calls, cached in data/cache
cskrill profile     # check field shapes and the detected Majors (do this!)
cskrill build       # writes data/out/
cskrill check major-winner-player "s1mple"
```

Re-running `fetch` costs nothing until you pass `--refresh`. Each full page
costs one extra call: it re-reads the last tournament on the page, because
rows that tie in LPDB's sort order can shift between pages.

## What `build` writes (data/out/)

| file | contents |
|---|---|
| `prompts.json` | each prompt: id, text, answer type, and every valid answer with expected pick share, tier and points |
| `entities.json` | display name and Liquipedia link for each answer (needed for attribution) |
| `alias_index.json` | normalised name → entity keys per type, for checking typed answers |
| `meta.json` | build date, tiers, attribution line |
| `report.txt` | per-prompt answer counts, tier spread, most common and rarest answers |

## Scoring

Before anyone plays, each answer's pick share is estimated from how well
known it is:

- **players and teams:** share ∝ (1 + prize money)^T × (1 + recent S-Tier top-4s)^(T·w)
- **cities, countries, organizers, maps:** share ∝ (1 + number of S-Tier events)^T

The defaults are T = 2 and w = 0.4. With T = 2, twice the prize money means
roughly 4× the picks. An answer's tier is the first one, starting from the most
common, whose minimum share it reaches. The tiers are named after CS2 ranks:
Silver (10 points), Gold Nova (25), Master Guardian (40), Legendary Eagle (60),
Supreme (80) and Global Elite (100). You can change all of this in `config.yaml`.

Once real answers arrive, blend them in with `cskrill.rarity.blend`:
q = (n + S·p) / (N + S), where S = `live_prior_strength`. The estimate fades
out as real play data builds up.

## Matching typed answers (port this to the game)

- `norm`: NFKD, drop accents, casefold, map ø/æ/œ/ł/đ/ð/þ/ı, turn `&` into
  "and", keep only `[a-z0-9]`.
- `leet`: 0→o 1→i 3→e 4→a 5→s 7→t.

The game looks up `leet(norm(text))`. Every entity with that key is a
candidate, so "device" can mean dev1ce. If nothing matches, small typos are
forgiven, but only when they point at exactly one entity (1 edit for 4–7
characters, 2 edits for 8 or more). The judge prefers a candidate that is a
valid answer for the prompt. If none is valid, it tells the player the name is
real but wrong (for example, NiKo for "won a Major"). Real names count too.
Team nicknames and alternate spellings live in `aliases.yaml`.

## Adding a prompt

```python
# cskrill/prompts.py
@builder
def iem_cologne_winners(ds, cfg):
    events = [t for t in ds.events(tier="1") if "cologne" in t.key.lower()]
    players, teams = ds.finishers(events, 1)
    yield Prompt("cologne-winner-player", "Name a player who has won IEM Cologne.",
                 "player", players, cfg.min_answers)
```

Prompts with fewer than `min_answers` answers are dropped and listed in the report.

## Liquipedia terms this follows

- custom User-Agent, gzip, one connection, throttled calls, backoff on HTTP 429
- results cached "for as long as possible", and the game never calls the API
- attribution: content is **CC-BY-SA 3.0**. Show `meta.json`'s attribution line
  in the game and link answers to their Liquipedia pages (`entities.json`)

## Known limits

- Liquipedia covers results, rosters and events, not per-map player stats
  (kills, rating). Stat prompts need another source later.
- Major detection and stage-page detection are heuristics. Check
  `cskrill profile`, and fix mistakes with `events.majors_include` /
  `majors_exclude`.
- Storage formats were checked against Liquipedia's own module code
  (github.com/Liquipedia/Lua-Modules): Majors are `publishertier = "Major
  Championship"`; game ids are `csgo`, `csgocs2` (events spanning both games)
  and `cs2`; tournament countries are ISO codes, mapped to names in
  `cskrill/countries.py`; roster players are `p1`, `p1dn`, `p1flag` (coaches
  are `c1`, skipped). Run `profile` after the first fetch anyway.
- If a team was renamed, results under its old name only merge when the old
  name is listed in `aliases.yaml`.
- `cskrill/sample.py` is approximate demo data, not a source of truth.
