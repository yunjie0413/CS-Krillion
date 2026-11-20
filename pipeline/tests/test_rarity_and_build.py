import json
import math
from datetime import date

import pytest

from cskrill.cli import main
from cskrill.config import DEFAULT_TIERS, Config, config_from_dict, load_aliases
from cskrill.export import build, write_outputs
from cskrill.model import Dataset
from cskrill.prompts import article
from cskrill.rarity import blend, prior_shares, tier_for
from cskrill.sample import sample_raw

DEMO = dict(min_answers=3, min_answers_small=3, many_majors=3, earnings_threshold=1_500_000)


def test_prior_is_a_power_law_and_sums_to_one():
    fam = {"a": math.log1p(2_000_000), "b": math.log1p(1_000_000), "c": math.log1p(500_000)}
    p = prior_shares(fam, temperature=2.0)
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["a"] / p["b"] == pytest.approx(4.0, rel=1e-3)  # twice the money, ~4x the picks
    flat = prior_shares({"x": 1.0, "y": 1.0, "z": 1.0}, 2.0)
    assert all(v == pytest.approx(1 / 3) for v in flat.values())


def test_blend_starts_at_prior_and_follows_live_counts():
    prior = {"a": 0.8, "b": 0.2}
    assert blend(prior, {}, 200) == prior
    late = blend(prior, {"a": 100, "b": 9900}, 200)
    assert late["b"] > 0.95


def test_tiers():
    assert tier_for(0.5, DEFAULT_TIERS).name == "Silver"
    assert tier_for(0.03, DEFAULT_TIERS).name == "Master Guardian"
    assert tier_for(0.0, DEFAULT_TIERS).name == "Global Elite"
    with pytest.raises(ValueError):
        config_from_dict({"rarity": {"tiers": [{"name": "A", "points": 1, "min_share": 0.5}]}})


def test_articles():
    assert [article(w) for w in ("American", "Estonian", "Ukrainian", "Uruguayan", "Danish")] == \
        ["an", "an", "a", "a", "a"]


@pytest.fixture(scope="module")
def sample_build():
    cfg = Config(**DEMO)
    ds = Dataset.from_raw(sample_raw(), cfg, load_aliases("aliases.yaml"))
    return ds, cfg, build(ds, cfg)


def answers(result, pid):
    return {a["key"] for a in next(p for p in result.prompts if p["id"] == pid)["answers"]}


def test_major_winners_exclude_stage_pages_and_runners_up(sample_build):
    _, _, result = sample_build
    winners = answers(result, "major-winner-player")
    assert {"S1mple", "Dev1ce", "Donk", "ZywOo", "Aleksib"} <= winners
    assert "NiKo" not in winners  # two Major finals, no title
    assert not any(k.startswith("Synth") for k in winners)


def test_cs2_era_prompts_skip_old_groups_and_tier2(sample_build):
    _, _, result = sample_build
    teams = answers(result, "s-tier-winner-team-cs2")
    assert teams == {"Natus_Vincere", "Team_Spirit", "Team_Vitality"}  # not G2 (IEM 2023, CS:GO)


def test_roster_prompt_drops_staff_and_pre_era_players(sample_build):
    _, _, result = sample_build
    navi = answers(result, "played-for-natus-vincere")
    assert "S1mple" in navi and "Synthetic_Coach" not in navi and "Synthetic_Oldtimer" not in navi


def test_labels_and_shares(sample_build):
    _, cfg, result = sample_build
    assert answers(result, "major-map") >= {"Dust_II", "Inferno", "Cobblestone"}
    for p in result.prompts:
        shares = [a["share"] for a in p["answers"]]
        assert sum(shares) == pytest.approx(1.0, abs=1e-4)
        assert shares == sorted(shares, reverse=True)
        mins = [next(t.min_share for t in cfg.tiers if t.name == a["tier"]) for a in p["answers"]]
        assert mins == sorted(mins, reverse=True)  # rarer answers never land in a commoner tier


def test_young_winner_prompt():
    raw = sample_raw()
    for row in raw["player"]:
        if row["pagename"] in ("Donk", "B1t", "M0NESY"):
            row["birthdate"] = {"Donk": "2007-01-25", "B1t": "2003-01-05", "M0NESY": "2005-05-01"}[row["pagename"]]
    cfg = Config(**DEMO)
    result = build(Dataset.from_raw(raw, cfg), cfg)
    young = next(p for p in result.dropped if p.id == "major-winner-teen")  # dropped: 2 answers < 3
    assert young.answers == {"Donk", "B1t"}  # m0NESY never won a Major in the sample


def test_write_outputs_and_cli_check(tmp_path, sample_build, capsys):
    ds, cfg, result = sample_build
    out = tmp_path / "out"
    write_outputs(out, ds, cfg, result)
    meta = json.loads((out / "meta.json").read_text())
    assert "Liquipedia" in meta["attribution"] and "CC-BY-SA" in meta["attribution"]
    index = json.loads((out / "alias_index.json").read_text())
    assert index["player"]["leet"]["simple"] == ["S1mple"]
    assert index["player"]["names"]["NiKo"] == "NiKo"  # non-answers too, for "real but wrong"
    entities = json.loads((out / "entities.json").read_text())
    assert entities["player"]["S1mple"]["url"].endswith("/counterstrike/S1mple")

    main(["--config", "missing.yaml", "check", "major-winner-player", "simple", "--out", str(out)])
    main(["--config", "missing.yaml", "check", "major-winner-player", "NiKo", "--out", str(out)])
    main(["--config", "missing.yaml", "check", "major-winner-team", "navi", "--out", str(out)])
    text = capsys.readouterr().out
    assert "s1mple: correct (leet)" in text
    assert "NiKo: a real player, but not a valid answer" in text
    assert "Natus Vincere: correct" in text


def test_demo_command_runs(tmp_path, capsys):
    main(["--config", "missing.yaml", "--data", str(tmp_path), "demo"])
    out = capsys.readouterr().out
    assert "Detected Majors" in out and "major-winner-player" in out
    assert (tmp_path / "sample" / "out" / "prompts.json").exists()


def test_config_file_parses():
    cfg = config_from_dict(__import__("yaml").safe_load(open("config.yaml")))
    assert cfg.era_start == date(2012, 8, 21) and cfg.tiers[0].name == "Silver"
    assert "Natus_Vincere" in cfg.squad_teams
