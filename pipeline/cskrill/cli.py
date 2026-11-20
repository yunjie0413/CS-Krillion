"""Command line: cskrill fetch | profile | build | check | demo."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .config import Config, load_aliases, load_config
from .export import build, load_outputs, write_outputs
from .fetch import load_raw, run_fetch
from .lpdb import LpdbClient, LpdbError
from .model import Dataset
from .names import Matcher
from .profile import profile_report
from .sample import sample_raw


def _dataset(raw_dir: Path, cfg: Config, aliases_path: str) -> Dataset:
    raw = load_raw(raw_dir)
    if not raw["tournament"]:
        sys.exit(f"No data in {raw_dir}. Run `cskrill fetch` first (or `cskrill demo`).")
    return Dataset.from_raw(raw, cfg, load_aliases(aliases_path))


def cmd_fetch(args: argparse.Namespace, cfg: Config) -> None:
    data = Path(args.data)
    try:
        # LIQUIPEDIA_USER_AGENT keeps your contact email out of the public repo
        user_agent = os.environ.get("LIQUIPEDIA_USER_AGENT") or cfg.user_agent
        client = LpdbClient(os.environ.get("LIQUIPEDIA_API_KEY"), user_agent, data / "cache",
                            min_interval=cfg.min_interval_s, max_retries=cfg.max_retries)
    except ValueError as exc:
        sys.exit(str(exc))
    tables = set(args.tables.split(",")) if args.tables else None
    try:
        counts = run_fetch(client, cfg, data / "raw", tables=tables, refresh=args.refresh)
    except LpdbError as exc:
        sys.exit(f"Fetch failed: {exc}")
    print(f"Done: {counts}. API calls: {client.requests_made}, cache hits: {client.cache_hits}.")
    print("Next: `cskrill profile` to check the data, then `cskrill build`.")


def cmd_build(raw_dir: Path, out_dir: Path, cfg: Config, aliases_path: str) -> None:
    ds = _dataset(raw_dir, cfg, aliases_path)
    result = build(ds, cfg)
    write_outputs(out_dir, ds, cfg, result)
    print((out_dir / "report.txt").read_text("utf-8"))
    print(f"Wrote {out_dir}/prompts.json, entities.json, alias_index.json, meta.json")


def cmd_check(args: argparse.Namespace, cfg: Config) -> None:
    prompts, index, entities = load_outputs(Path(args.out))
    prompt = next((p for p in prompts if p["id"] == args.prompt_id), None)
    if prompt is None:
        sys.exit("Unknown prompt id. Available: " + ", ".join(p["id"] for p in prompts))
    idx = index[prompt["type"]]
    matcher = Matcher(idx["exact"], idx["leet"], fuzzy=cfg.fuzzy)
    by_key = {a["key"]: a for a in prompt["answers"]}
    text = " ".join(args.answer)
    # if a name fits several valid answers, credit the best-known one (likeliest intent)
    verdict = matcher.judge(text, set(by_key), {k: a["share"] for k, a in by_key.items()})
    print(prompt["text"])
    if verdict.status == "correct":
        a = by_key[verdict.key]
        print(f"  '{text}' -> {a['name']}: correct ({verdict.how}), {a['tier']} (+{a['points']}), "
              f"expected pick share {a['share']:.2%}")
    elif verdict.status == "wrong":
        name = entities.get(prompt["type"], {}).get(verdict.key, {}).get("name", verdict.key)
        print(f"  '{text}' -> {name}: a real {prompt['type']}, but not a valid answer")
    else:
        print(f"  '{text}': no match")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="cskrill", description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--aliases", default="aliases.yaml")
    ap.add_argument("--data", default="data", help="data directory (cache/, raw/, out/)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download LPDB tables (needs LIQUIPEDIA_API_KEY)")
    f.add_argument("--refresh", action="store_true", help="ignore the cache and re-download")
    f.add_argument("--tables", help="comma list, e.g. tournament,placement")
    sub.add_parser("profile", help="print value distributions and detected Majors")
    sub.add_parser("build", help="build prompts and answer sets into data/out")
    c = sub.add_parser("check", help="test an answer: cskrill check major-winner-player s1mple")
    c.add_argument("prompt_id")
    c.add_argument("answer", nargs="+")
    c.add_argument("--out", default=None, help="output dir to read (default: <data>/out)")
    sub.add_parser("demo", help="build from the bundled sample data, no API key needed")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config(args.config) if Path(args.config).exists() else Config()
    data = Path(args.data)

    if args.cmd == "fetch":
        cmd_fetch(args, cfg)
    elif args.cmd == "profile":
        print(profile_report(load_raw(data / "raw"), cfg, load_aliases(args.aliases)))
    elif args.cmd == "build":
        cmd_build(data / "raw", data / "out", cfg, args.aliases)
    elif args.cmd == "check":
        args.out = args.out or str(data / "out")
        cmd_check(args, cfg)
    elif args.cmd == "demo":
        raw_dir, out_dir = data / "sample" / "raw", data / "sample" / "out"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for name, rows in sample_raw().items():
            (raw_dir / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
        demo_cfg = cfg.with_overrides(min_answers=3, min_answers_small=3, many_majors=3,
                                      earnings_threshold=1_500_000,
                                      squad_teams=("Natus_Vincere", "Astralis"))
        print(profile_report(load_raw(raw_dir), demo_cfg, load_aliases(args.aliases)))
        print("\n" + "=" * 70 + "\n")
        cmd_build(raw_dir, out_dir, demo_cfg, args.aliases)
        print(f"Try: cskrill check major-winner-player s1mple --out {out_dir}")


if __name__ == "__main__":
    main()
