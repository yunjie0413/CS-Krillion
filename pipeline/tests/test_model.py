from datetime import date

from cskrill.config import Config
from cskrill.model import (
    Dataset, as_name_list, canon, opponent_players, parse_date, parse_location, parse_place,
)


def test_parsers():
    assert canon("natus vincere") == "Natus_vincere"
    assert canon("PGL/2024/Copenhagen") == "PGL/2024/Copenhagen"
    assert parse_place("1") == (1, 1) and parse_place("3-4") == (3, 4) and parse_place("W") is None
    assert parse_date("2024-03-31 00:00:00") == date(2024, 3, 31)
    assert parse_date("0000-00-00") is None and parse_date("1970-01-01") is None


def test_list_fields_in_every_shape():
    expected = ["Ancient", "Dust II"]
    assert as_name_list("Ancient;Dust II") == expected
    assert as_name_list('["Ancient", "Dust II"]') == expected
    assert as_name_list({"map1": "Ancient", "map2": "Dust II"}, "map") == expected
    assert as_name_list([{"name": "Ancient"}, {"link": "Dust II"}]) == expected
    assert as_name_list('{"organizer1":"PGL","organizer1link":"PGL"}', "organizer") == ["PGL"]


def test_locations_and_opponents():
    assert parse_location({"city1": "Cologne", "country1": "Germany"}) == ("Cologne", "Germany")
    assert parse_location('{"country1": "Brazil", "city1": "Rio de Janeiro"}') == ("Rio de Janeiro", "Brazil")
    assert parse_location("Austin, United States") == ("Austin", "United States")
    opp = {"p2": "ropz", "p2flag": "Estonia", "p1": "karrigan", "p1dn": "karrigan", "c1": "coach"}
    assert opponent_players(opp) == [("Karrigan", "karrigan", ""), ("Ropz", "ropz", "Estonia")]


def _ds(tournaments, placements, **cfg):
    return Dataset.from_raw({"tournament": tournaments, "placement": placements}, Config(**cfg))


def _t(page, name, tier="1", end="2024-06-01", game="cs2", pt="", kind="Offline"):
    return {"pagename": page, "name": name, "liquipediatier": tier, "enddate": end,
            "game": game, "publishertier": pt, "type": kind}


def _p(page, place, team, players):
    opp = {f"p{i}": p for i, p in enumerate(players, 1)}
    return {"pagename": page, "placement": place, "opponentname": team, "opponenttype": "team",
            "opponentplayers": opp}


def test_major_detection_top_level_and_stage_pages():
    ds = _ds([
        _t("PGL/2024/Copenhagen", "PGL CS2 Major Copenhagen 2024", pt="major"),
        _t("PGL/2024/Copenhagen/Opening_Stage", "PGL CS2 Major Copenhagen 2024 - Opening Stage", pt="major"),
        _t("PGL/2024/Copenhagen_RMR", "PGL Major RMR Europe", pt=""),
        _t("Some/Cup/Groups", "Some Cup Groups"),
    ], [])
    majors = [t.key for t in ds.major_events()]
    assert majors == ["PGL/2024/Copenhagen"]
    assert ds.is_stage(ds.tournaments["Some/Cup/Groups"])


def test_era_and_game_filter():
    ds = _ds([_t("Old/1", "Old Major", end="2010-01-01", game="cs16"),
              _t("New/1", "New Major", end="2024-01-01")], [], era_start=date(2012, 8, 21))
    assert [t.key for t in ds.events(tier="1")] == ["New/1"]


def test_team_resolution_via_aliases_and_stub_players():
    raw = {
        "team": [{"pagename": "MOUZ", "name": "MOUZ", "template": "mouz"}],
        "tournament": [_t("E/1", "Event")],
        "placement": [_p("E/1", "1", "mousesports", ["Frozen", "Ropz"])],
    }
    ds = Dataset.from_raw(raw, Config(), {"teams": {"MOUZ": ["mousesports"]}})
    pl = ds.placements_at("E/1")[0]
    assert pl.team == "MOUZ"
    assert set(ds.players) == {"Frozen", "Ropz"}


def test_label_merging_through_aliases():
    raw = {"tournament": [
        {**_t("A/1", "A"), "maps": "Dust2;Inferno"},
        {**_t("B/1", "B"), "maps": ["Dust II", "de_inferno"]},
    ]}
    ds = Dataset.from_raw(raw, Config(), {"maps": {"Dust II": ["Dust2"]}})
    assert ds.tournaments["A/1"].maps == ["Dust_II", "Inferno"]
    assert ds.tournaments["B/1"].maps == ["Dust_II", "Inferno"]
    assert ds.display("map", "Dust_II") == "Dust II"
    assert ds.label_counts["map"]["Dust_II"] == 2


def test_csgocs2_events_count_and_major_qualifiers_do_not():
    ds = _ds([_t("T/1", "Transition Cup", game="csgocs2"),
              _t("Q/1", "Major Contenders Showdown", pt="Major Qualifier"),
              _t("M/1", "Some Major 2019", pt="Major Championship", game="csgo")], [])
    assert {t.key for t in ds.events(tier="1")} == {"T/1", "Q/1", "M/1"}
    assert [t.key for t in ds.major_events()] == ["M/1"]


def test_country_codes_become_names():
    raw = {"tournament": [{**_t("A/1", "A"), "locations": {"city1": "Cologne", "country1": "de", "region1": "Europe"}},
                          {**_t("B/1", "B"), "locations": {"city1": "Columbus", "country1": "US"}}]}
    ds = Dataset.from_raw(raw, Config(), {"countries": {"United States": ["USA"]}})
    assert ds.display("country", ds.tournaments["A/1"].country) == "Germany"
    assert ds.tournaments["B/1"].country == "United_States"
