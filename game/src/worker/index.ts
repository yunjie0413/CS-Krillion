// Cloudflare Worker: serves the API; static files come from ./public (Workers assets).
//
//   GET  /api/day                     today's info (no prompt text)
//   POST /api/start   {round}         opens a round and starts its timer
//   POST /api/guess   {day, round, text}
//   GET  /api/reveal?day=&round=      common and rare answers, once the round is over
//   GET  /api/summary?day=            totals and share text
//
// Players are anonymous: a random id in an HttpOnly cookie.

import { Game, GameError } from "../core/game.ts";
import type { Pack, Schedule } from "../core/pack.ts";
import { dayId } from "../core/schedule.ts";
import packJson from "../data/pack.json";
import scheduleJson from "../data/schedule.json";
import { D1Store } from "./d1store.ts";

export interface Env {
  DB: D1Database;
  ASSETS: Fetcher;
}

const pack = packJson as unknown as Pack;
const schedule = scheduleJson as Schedule;
const COOKIE = "ckr";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(req);

    const { run, setCookie } = runId(req);
    const game = new Game(pack, schedule, new D1Store(env.DB));
    const now = Date.now();
    try {
      const q = url.searchParams;
      let body: unknown;
      switch (`${req.method} ${url.pathname}`) {
        case "GET /api/day":
          body = game.info(now);
          break;
        case "POST /api/start": {
          const b = await readJson(req);
          body = await game.start(run, int(b.round), now);
          break;
        }
        case "POST /api/guess": {
          const b = await readJson(req);
          body = await game.guess(run, day(b.day), int(b.round), String(b.text ?? "").slice(0, 80), now);
          break;
        }
        case "GET /api/reveal":
          body = await game.reveal(run, day(q.get("day")), int(q.get("round")), now);
          break;
        case "GET /api/summary":
          body = await game.summary(run, day(q.get("day") ?? dayId(now)), now);
          break;
        default:
          return json({ error: "Not found" }, 404, setCookie);
      }
      return json(body, 200, setCookie);
    } catch (e) {
      if (e instanceof GameError) return json({ error: e.message }, e.status, setCookie);
      console.error(e);
      return json({ error: "Server error" }, 500, setCookie);
    }
  },
} satisfies ExportedHandler<Env>;

function runId(req: Request): { run: string; setCookie: string | null } {
  const cookies = req.headers.get("Cookie") ?? "";
  const m = cookies.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  if (m && UUID.test(m[1])) return { run: m[1], setCookie: null };
  const run = crypto.randomUUID();
  return { run, setCookie: `${COOKIE}=${run}; Path=/; Max-Age=31536000; HttpOnly; Secure; SameSite=Lax` };
}

async function readJson(req: Request): Promise<Record<string, unknown>> {
  try {
    const b = await req.json();
    if (b && typeof b === "object") return b as Record<string, unknown>;
  } catch {
    /* fall through */
  }
  throw new GameError(400, "Expected a JSON body.");
}

function int(v: unknown): number {
  const n = Number(v);
  if (!Number.isInteger(n)) throw new GameError(400, "Bad round number.");
  return n;
}

function day(v: unknown): string {
  const s = String(v ?? "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) throw new GameError(400, "Bad day.");
  return s;
}

function json(body: unknown, status: number, setCookie: string | null): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json", "Cache-Control": "no-store" };
  if (setCookie) headers["Set-Cookie"] = setCookie;
  return new Response(JSON.stringify(body), { status, headers });
}
