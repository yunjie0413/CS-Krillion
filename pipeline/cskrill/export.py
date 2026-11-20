"""Build every prompt, score its answers, and write the files the game reads.

data/out/
  prompts.json      prompts with answers, prior shares, tiers and points
  entities.json     display names + Liquipedia links for every answer
  alias_index.json  per type: normalised name -> entity keys, plus display names
  meta.json         build info, tiers, attribution
  report.txt        human-readable summary to sanity-check the build
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config
from .model import ALIAS_SECTIONS, LABEL_TYPES, Dataset, canon
from .names import build_index, page_to_label, team_name_variants
from .prompts import Prompt, build_prompts
from .rarity import familiarity, prior_shares, tier_for

LICENSE_URL = "https://creativecommons.org/licenses/by-sa/3.0/"


@dataclass
class BuildResult:
    prompts: list[dict[str, Any]]
    dropped: list[Prompt]


def universe(ds: Dataset, etype: str, cfg: Config) -> dict[str, set[str]]:
    """Every entity of a type with all the names a player might type for it."""
    extra = ds.aliases.get(ALIAS_SECTIONS.get(etype, ""), {})
    out: dict[str, set[str]] = {}
    if etype == "player":
        for k, p in ds.players.items():
            names = {p.handle, page_to_label(k), *p.alt_ids, *extra.get(k, [])}
            if cfg.accept_real_names and p.real_name:
                names.add(p.real_name)
            out[k] = {n for n in names if n}
    elif etype == "team":
        for k, t in ds.teams.items():
            names = team_name_variants(t.name) | {page_to_label(k), t.template, *extra.get(k, [])}
            out[k] = {n for n in names if n}
    elif etype in LABEL_TYPES:
        extra_by_key: dict[str, list[str]] = {}
        for label, names in extra.items():
            extra_by_key.setdefault(canon(label), []).extend([label, *names])
        for k, label in ds.labels[etype].items():
            out[k] = {label, page_to_label(k), *extra_by_key.get(k, [])}
    return out


def build(ds: Dataset, cfg: Config) -> BuildResult:
    kept: list[dict[str, Any]] = []
    dropped: list[Prompt] = []
    for p in build_prompts(ds, cfg):
        if len(p.answers) < p.min_answers:
            dropped.append(p)
            continue
        shares = prior_shares(familiarity(p.etype, p.answers, ds, cfg), cfg.temperature)
        answers = []
        for key in sorted(p.answers, key=lambda k: (-shares[k], k)):
            tier = tier_for(shares[key], cfg.tiers)
            answers.append({"key": key, "name": ds.display(p.etype, key),
                            "share": round(shares[key], 6), "tier": tier.name, "points": tier.points})
        kept.append({
            "id": p.id,
            "text": p.text,
            "type": p.etype,
            "answer_count": len(answers),
            "tiers": dict(Counter(a["tier"] for a in answers)),
            "answers": answers,
        })
    return BuildResult(kept, dropped)


def entity_record(ds: Dataset, etype: str, key: str, wiki: str) -> dict[str, Any]:
    rec: dict[str, Any] = {"name": ds.display(etype, key)}
    if etype == "player" and key in ds.players:
        p = ds.players[key]
        rec.update({"nationality": p.nationality, "url": f"https://liquipedia.net/{wiki}/{key}"})
    elif etype == "team":
        rec["url"] = f"https://liquipedia.net/{wiki}/{key}"
    elif etype == "map":
        rec["url"] = f"https://liquipedia.net/{wiki}/{key}"
    return rec


def write_outputs(out_dir: Path, ds: Dataset, cfg: Config, result: BuildResult) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    used_types = sorted({p["type"] for p in result.prompts})

    entities: dict[str, dict[str, Any]] = {t: {} for t in used_types}
    for p in result.prompts:
        for a in p["answers"]:
            entities[p["type"]][a["key"]] = entity_record(ds, p["type"], a["key"], cfg.wiki)

    index: dict[str, Any] = {}
    for etype in used_types:
        uni = universe(ds, etype, cfg)
        exact, leet_keys = build_index(uni)
        index[etype] = {"exact": {k: sorted(v) for k, v in sorted(exact.items())},
                        "leet": {k: sorted(v) for k, v in sorted(leet_keys.items())},
                        "names": {k: ds.display(etype, k) for k in sorted(uni)}}

    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data_through": ds.latest.isoformat() if ds.latest else None,
        "era_start": cfg.era_start.isoformat(),
        "prompt_count": len(result.prompts),
        "tiers": [{"name": t.name, "points": t.points, "min_share": t.min_share} for t in cfg.tiers],
        "live_prior_strength": cfg.live_prior_strength,
        "attribution": f"Data from Liquipedia (https://liquipedia.net/{cfg.wiki}), licensed CC-BY-SA 3.0.",
        "license_url": LICENSE_URL,
    }

    def dump(name: str, obj: Any) -> None:
        (out_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")

    dump("prompts.json", result.prompts)
    dump("entities.json", entities)
    dump("alias_index.json", index)
    dump("meta.json", meta)
    (out_dir / "report.txt").write_text(report(result, cfg), "utf-8")


def report(result: BuildResult, cfg: Config) -> str:
    short = {t.name: t.name.replace(" ", "")[:4] for t in cfg.tiers}
    legend = ", ".join(f"{short[t.name]}={t.name} ({t.points})" for t in cfg.tiers)
    lines = [f"{len(result.prompts)} prompts kept, {len(result.dropped)} dropped (too few answers)",
             f"Answers per tier: {legend}", ""]
    for p in result.prompts:
        spread = " ".join(f"{short[t.name]}:{p['tiers'].get(t.name, 0)}" for t in cfg.tiers)
        common = ", ".join(a["name"] for a in p["answers"][:3])
        rare = ", ".join(a["name"] for a in p["answers"][-3:])
        lines.append(f"{p['id']:<36} {p['answer_count']:>4}  [{spread}]")
        lines.append(f"    {p['text']}")
        lines.append(f"    most common: {common}   rarest: {rare}")
    if result.dropped:
        lines += ["", "Dropped:"]
        lines += [f"  {p.id:<36} {len(p.answers):>3} < {p.min_answers}" for p in result.dropped]
    return "\n".join(lines) + "\n"


def load_outputs(out_dir: Path) -> tuple[list[dict[str, Any]], Mapping[str, Any], Mapping[str, Any]]:
    prompts = json.loads((out_dir / "prompts.json").read_text("utf-8"))
    index = json.loads((out_dir / "alias_index.json").read_text("utf-8"))
    entities = json.loads((out_dir / "entities.json").read_text("utf-8"))
    return prompts, index, entities
