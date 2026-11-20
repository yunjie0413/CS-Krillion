// The game page. Screens: home -> 7 rounds (each ends with a reveal) -> scoreboard.

import { GRACE_MS } from "../core/game.ts";
import type { DayInfo, GuessResult, Reveal, RoundResult, StartResult, Summary } from "../core/game.ts";
import type { GameApi } from "./api.ts";

type Child = Node | string | null | undefined | false;
type Attrs = Record<string, string | number | boolean | EventListener | undefined>;

function h<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Attrs = {}, ...kids: Child[]): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === false) continue;
    if (typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids) if (kid) el.append(kid);
  return el;
}

const SHORT: Record<string, string> = {
  "Silver": "S", "Gold Nova": "GN", "Master Guardian": "MG", "Legendary Eagle": "LE", "Supreme": "SMFC", "Global Elite": "GE",
};
const pct = (share: number) => (share >= 0.1 ? `${Math.round(share * 100)}%` : `${(share * 100).toFixed(1)}%`);
const clock = (ms: number) => {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};
const niceDay = (day: string) =>
  new Date(`${day}T12:00:00Z`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });

export interface AppOptions {
  prototype?: { note: string; shiftDay: (by: number) => void };
}

export class App {
  private api: GameApi;
  private root: HTMLElement;
  private opts: AppOptions;
  private info!: DayInfo;
  private results: (RoundResult | null)[] = [];
  private round = 0;
  private deadline = 0;
  private skew = 0;
  private timer: ReturnType<typeof setInterval> | undefined;
  private busy = false;
  private el: Record<string, HTMLElement> = {};

  constructor(root: HTMLElement, api: GameApi, opts: AppOptions = {}) {
    this.root = root;
    this.api = api;
    this.opts = opts;
  }

  async boot(): Promise<void> {
    this.stopTimer();
    try {
      this.info = await this.api.info();
      this.results = (await this.api.summary(this.info.day)).rounds;
      this.home();
    } catch (e) {
      this.fail(e);
    }
  }

  // ---- screens ------------------------------------------------------------

  private screen(...kids: Child[]): void {
    const p = this.opts.prototype;
    const banner = p
      ? h("div", { class: "proto" },
        h("span", {}, p.note),
        h("span", { class: "proto-day" },
          h("button", { type: "button", "aria-label": "Previous day", onclick: () => p.shiftDay(-1) }, "‹"),
          h("span", {}, niceDay(this.info.day)),
          h("button", { type: "button", "aria-label": "Next day", onclick: () => p.shiftDay(1) }, "›")))
      : null;
    this.root.replaceChildren(...[banner, h("main", { class: "stage" }, ...kids), this.footer()].filter(Boolean) as Node[]);
  }

  private home(): void {
    const done = this.results.filter(Boolean).length;
    const next = this.results.findIndex((r) => r === null) + 1;
    const label = done === 0 ? "Start" : next > 0 ? `Continue · round ${next}` : "See today's scoreboard";
    this.screen(
      h("header", { class: "masthead" },
        h("p", { class: "kicker" }, `${niceDay(this.info.day)} · ${this.info.rounds} prompts · ${this.info.round_ms / 1000} s each`),
        h("h1", { class: "wordmark" }, "CS", h("span", {}, "-"), "Krillion"),
        h("p", { class: "lede" }, "Name a player, team, city or map that fits the prompt. The fewer people who'd think of your answer, the higher it ranks.")),
      this.pips(),
      h("ol", { class: "ladder", "aria-label": "Ranks, most common to rarest" },
        ...this.info.tiers.map((t) => h("li", {}, this.badge(t.name), h("span", { class: "ladder-name" }, t.name), h("span", { class: "ladder-pts" }, `${t.points}`)))),
      h("ul", { class: "rules" },
        h("li", {}, "Wrong guesses cost nothing. Keep typing until the clock runs out."),
        h("li", {}, "One correct answer per prompt. Nicknames, real names and small typos count.")),
      h("button", { class: "cta", type: "button", onclick: () => (next > 0 ? this.startRound(next) : this.scoreboard()) }, label),
    );
  }

  private async startRound(round: number): Promise<void> {
    this.round = round;
    let s: StartResult;
    try {
      s = await this.api.start(round);
    } catch (e) {
      return this.fail(e);
    }
    this.skew = s.now - Date.now();
    this.deadline = s.deadline;

    const input = h("input", {
      id: "guess", class: "guess", type: "text", autocomplete: "off", autocapitalize: "off", spellcheck: "false",
      enterkeyhint: "go", maxlength: 80, placeholder: "Type an answer", "aria-label": "Your answer",
    });
    const form = h("form", { class: "answer", onsubmit: (e: Event) => { e.preventDefault(); this.submit(); } },
      input, h("button", { class: "fire", type: "submit" }, "Guess"));
    this.el = {
      clock: h("div", { class: "clock", role: "timer", "aria-live": "off" }, clock(s.deadline - s.now)),
      bar: h("div", { class: "fuse" }, h("i", {})),
      feed: h("ol", { class: "feed", "aria-live": "polite", "aria-label": "Your guesses" }),
      input, form,
      after: h("div", { class: "after" }),
      pips: this.pips(round),
      score: h("b", {}, `${this.total()}`),
    };
    this.screen(
      h("div", { class: "hud" }, this.el.pips, this.el.clock, h("div", { class: "score" }, this.el.score, " pts")),
      this.el.bar,
      h("p", { class: "round-no" }, `Round ${round} of ${this.info.rounds}`),
      h("h2", { class: "prompt" }, s.text),
      this.el.form,
      this.el.feed,
      this.el.after,
    );
    if (s.finished) return this.finishRound(s.finished);
    input.focus();
    this.tick();
    this.timer = setInterval(() => this.tick(), 100);
  }

  private tick(): void {
    const left = this.deadline - (Date.now() + this.skew);
    this.el.clock.textContent = clock(left);
    this.el.clock.classList.toggle("low", left <= 5000);
    (this.el.bar.firstChild as HTMLElement).style.transform = `scaleX(${Math.max(0, left) / this.info.round_ms})`;
    if (left <= 0) this.timeUp();
  }

  private async submit(): Promise<void> {
    const input = this.el.input as HTMLInputElement;
    const text = input.value.trim();
    if (!text || this.busy) return;
    this.busy = true;
    let r: GuessResult;
    try {
      r = await this.api.guess(this.info.day, this.round, text);
    } catch (e) {
      this.busy = false;
      return this.feed("bad", text, e instanceof Error ? e.message : "Couldn't send that guess.");
    }
    this.busy = false;
    switch (r.status) {
      case "correct":
        this.stopTimer();
        this.feed("hit", r.name, `${r.tier} +${r.points}`);
        return this.finishRound({ round: this.round, text: "", answer: { name: r.name, tier: r.tier, points: r.points }, points: r.points });
      case "wrong":
        this.feed("miss", r.name, "real, but doesn't fit");
        break;
      case "unknown":
        this.feed("miss", text, "not recognised");
        break;
      case "limit":
        this.feed("bad", text, "guess limit reached for this round");
        break;
      case "timeout":
        return this.timeUp();
      case "done":
        this.stopTimer();
        return this.finishRound(r.result);
    }
    input.select();
  }

  private feed(kind: "hit" | "miss" | "bad", what: string, why: string): void {
    this.el.feed.prepend(h("li", { class: `kf kf-${kind}` }, h("b", {}, what), h("span", {}, why)));
  }

  private timeUp(): void {
    if (!this.timer && this.el.form.classList.contains("locked")) return;
    this.stopTimer();
    this.lock();
    this.el.clock.textContent = "0:00";
    this.feed("bad", "Time's up", "no answer this round");
    // The server allows a short grace period for latency; ask once it has passed.
    setTimeout(async () => {
      try {
        const rev = await this.api.reveal(this.info.day, this.round);
        this.finishRound(rev.yours, rev);
      } catch (e) {
        this.fail(e);
      }
    }, GRACE_MS + 200);
  }

  private async finishRound(result: RoundResult, reveal?: Reveal): Promise<void> {
    this.lock();
    this.el.clock.classList.add("done");
    this.results[this.round - 1] = result;
    this.el.score.textContent = `${this.total()}`;
    const pips = this.pips(this.round);
    this.el.pips.replaceWith(pips);
    this.el.pips = pips;
    const last = this.round >= this.info.rounds;
    const next = h("button", {
      class: "cta", type: "button",
      onclick: () => (last ? this.scoreboard() : this.startRound(this.round + 1)),
    }, last ? "See the scoreboard" : `Next round · ${this.round + 1} of ${this.info.rounds}`);

    const a = result.answer;
    const head = a
      ? h("div", { class: `reveal-rank ${this.tierClass(a.tier)}` },
        this.badge(a.tier, true),
        h("div", {},
          h("p", { class: "reveal-name" }, a.name),
          h("p", { class: "reveal-tier" }, `${a.tier} · +${a.points}`)))
      : h("div", { class: "reveal-rank none" }, h("p", { class: "reveal-name" }, "No answer"), h("p", { class: "reveal-tier" }, "0 points"));
    this.el.after.replaceChildren(head, h("p", { class: "loading" }, "Loading answers…"));
    next.focus();

    try {
      reveal ??= await this.api.reveal(this.info.day, this.round);
    } catch {
      this.el.after.replaceChildren(head, next);
      next.focus();
      return;
    }
    const list = (title: string, items: Reveal["common"]) =>
      h("div", { class: "board" }, h("h3", {}, title),
        h("ol", {}, ...items.map((x) => h("li", {}, this.badge(x.tier), h("span", { class: "board-name" }, x.name), h("span", { class: "board-pct" }, pct(x.share))))));
    this.el.after.replaceChildren(
      head,
      h("div", { class: "boards" },
        list("Most picked", reveal.common),
        reveal.rare.length ? list("Rarest", reveal.rare) : null),
      h("p", { class: "board-note" }, `${reveal.answer_count} valid answers. Percentages are expected shares of players.`),
      next,
    );
    next.focus();
  }

  private async scoreboard(): Promise<void> {
    this.stopTimer();
    let s: Summary;
    try {
      s = await this.api.summary(this.info.day);
    } catch (e) {
      return this.fail(e);
    }
    this.results = s.rounds;
    const share = h("pre", { class: "share-text" }, s.share_text);
    const copy = h("button", { class: "cta ghost", type: "button" }, "Copy result");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(s.share_text);
        copy.textContent = "Copied";
      } catch {
        getSelection()?.selectAllChildren(share);
        copy.textContent = "Selected: press copy";
      }
    });
    const hours = Math.max(0, this.info.ends_at - Date.now() - this.skew) / 3_600_000;
    this.screen(
      h("header", { class: "masthead" },
        h("p", { class: "kicker" }, niceDay(s.day)),
        h("h1", { class: "total" }, `${s.total}`, h("span", {}, ` / ${s.max}`)),
        h("p", { class: "lede" }, s.complete ? "Today's run is done." : "Some rounds are still open.")),
      h("div", { class: "table-wrap" },
        h("table", { class: "scoreboard" },
          h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Prompt"), h("th", {}, "Answer"), h("th", { class: "num" }, "Pts"))),
          h("tbody", {}, ...s.rounds.map((r, i) => h("tr", {},
            h("td", { class: "num" }, `${i + 1}`),
            h("td", {}, r?.text ?? "Not played"),
            h("td", {}, r?.answer ? h("span", { class: "cell-answer" }, this.badge(r.answer.tier), r.answer.name) : h("span", { class: "muted" }, r ? "Time's up" : "–")),
            h("td", { class: "num" }, `${r?.points ?? 0}`)))))),
      share,
      h("div", { class: "row" }, copy,
        s.complete ? null : h("button", { class: "cta", type: "button", onclick: () => this.home() }, "Back to today")),
      h("p", { class: "board-note" }, `New prompts in about ${hours < 1 ? `${Math.ceil(hours * 60)} min` : `${Math.floor(hours)} h ${Math.round((hours % 1) * 60)} min`}.`),
    );
  }

  private fail(e: unknown): void {
    this.stopTimer();
    const msg = e instanceof Error ? e.message : "Something went wrong.";
    this.root.replaceChildren(h("main", { class: "stage" },
      h("h2", { class: "prompt" }, "That didn't load"),
      h("p", { class: "lede" }, msg),
      h("button", { class: "cta", type: "button", onclick: () => this.boot() }, "Try again")));
  }

  // ---- pieces -------------------------------------------------------------

  private pips(current = 0): HTMLElement {
    return h("ol", { class: "pips", "aria-label": "Rounds" }, ...Array.from({ length: this.info.rounds }, (_, i) => {
      const r = this.results[i];
      const cls = ["pip", r?.answer ? this.tierClass(r.answer.tier) : r ? "pip-miss" : "", i + 1 === current ? "pip-now" : ""].join(" ");
      return h("li", { class: cls, "aria-label": `Round ${i + 1}${r?.answer ? `: ${r.answer.tier}` : r ? ": missed" : ""}` });
    }));
  }

  private badge(tier: string, big = false): HTMLElement {
    return h("span", { class: `badge ${this.tierClass(tier)}${big ? " badge-big" : ""}`, "aria-hidden": "true" }, SHORT[tier] ?? tier.slice(0, 2).toUpperCase());
  }

  private tierClass(tier: string): string {
    const i = this.info.tiers.findIndex((t) => t.name === tier);
    return `t${Math.max(0, i)}`;
  }

  private total(): number {
    return this.results.reduce((s, r) => s + (r?.points ?? 0), 0);
  }

  private lock(): void {
    this.el.form?.classList.add("locked");
    this.el.form?.querySelectorAll("input, button").forEach((x) => ((x as HTMLInputElement).disabled = true));
  }

  private stopTimer(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }

  private footer(): HTMLElement {
    const p = this.opts.prototype;
    return h("footer", { class: "credit" },
      p ? "Sample data for testing. Real answers will come from " : "Answers from ",
      h("a", { href: "https://liquipedia.net/counterstrike", target: "_blank", rel: "noopener" }, "Liquipedia"),
      ", licensed ",
      h("a", { href: this.info.license_url, target: "_blank", rel: "noopener" }, "CC-BY-SA 3.0"),
      ". Fan project, not affiliated with Valve.");
  }
}
