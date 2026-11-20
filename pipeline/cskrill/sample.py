"""Hand-made sample shaped like LPDB responses, for `cskrill demo` and the tests.

This is small and NOT authoritative: rosters, earnings, dates and map pools
are approximate, and there are no birthdates. Real data comes from
`cskrill fetch`. Rows named "Synthetic ..." are invented to exercise edge
cases: a Major stage sub-page, a group-stage page, a tier-2 event, a CS 1.6
event, staff rows in a roster, and fields arriving in different shapes.
"""

from __future__ import annotations

import json
from itertools import count
from typing import Any

_ids = count(1000)

# page key -> (display name, flag)
P: dict[str, tuple[str, str]] = {
    "Aleksib": ("Aleksib", "Finland"), "IM": ("iM", "Romania"), "B1t": ("b1t", "Ukraine"),
    "JL": ("jL", "Lithuania"), "W0nderful": ("w0nderful", "Ukraine"),
    "Karrigan": ("karrigan", "Denmark"), "Rain": ("rain", "Norway"), "Frozen": ("frozen", "Slovakia"),
    "Ropz": ("ropz", "Estonia"), "Broky": ("broky", "Latvia"),
    "Chopper": ("chopper", "Russia"), "Sh1ro": ("sh1ro", "Russia"), "Magixx": ("magixx", "Russia"),
    "Zont1x": ("zont1x", "Ukraine"), "Donk": ("donk", "Russia"),
    "ApEX": ("apEX", "France"), "ZywOo": ("ZywOo", "France"), "FlameZ": ("flameZ", "Israel"),
    "Mezii": ("mezii", "United Kingdom"),
    "BLitz": ("bLitz", "Mongolia"), "Techno4K": ("Techno4K", "Mongolia"), "Senzu": ("Senzu", "Mongolia"),
    "Mzinho": ("mzinho", "Mongolia"), "910": ("910", "Mongolia"),
    "Twistzz": ("Twistzz", "Canada"), "S1mple": ("s1mple", "Ukraine"),
    "ElectroNic": ("electroNic", "Russia"), "Perfecto": ("Perfecto", "Russia"), "Sdy": ("sdy", "Ukraine"),
    "Jame": ("Jame", "Russia"), "Qikert": ("qikert", "Kazakhstan"), "FL1T": ("FL1T", "Russia"),
    "Fame": ("fame", "Russia"), "N0rb3r7": ("n0rb3r7", "Russia"),
    "CadiaN": ("cadiaN", "Denmark"), "Stavn": ("stavn", "Denmark"), "TeSeS": ("TeSeS", "Denmark"),
    "Sjuush": ("sjuush", "Denmark"), "Refrezh": ("refrezh", "Denmark"),
    "Boombl4": ("Boombl4", "Russia"), "NiKo": ("NiKo", "Bosnia and Herzegovina"),
    "HuNter-": ("huNter-", "Bosnia and Herzegovina"), "Nexa": ("nexa", "Serbia"),
    "AmaNEk": ("AmaNEk", "France"), "JaCkz": ("JaCkz", "France"),
    "Dev1ce": ("dev1ce", "Denmark"), "Dupreeh": ("dupreeh", "Denmark"), "Xyp9x": ("Xyp9x", "Denmark"),
    "Gla1ve": ("gla1ve", "Denmark"), "Magisk": ("Magisk", "Denmark"),
    "Allu": ("allu", "Finland"), "Aerial": ("Aerial", "Finland"), "XseveN": ("xseveN", "Finland"),
    "Sergej": ("sergej", "Finland"),
    "Edward": ("Edward", "Ukraine"), "Zeus": ("Zeus", "Ukraine"), "Flamie": ("flamie", "Russia"),
    "Skadoodle": ("Skadoodle", "United States"), "Stewie2K": ("Stewie2K", "United States"),
    "Tarik": ("tarik", "United States"), "RUSH": ("RUSH", "United States"),
    "Autimatic": ("autimatic", "United States"),
    "Olofmeister": ("olofmeister", "Sweden"), "GuardiaN": ("GuardiaN", "Slovakia"),
    "M0NESY": ("m0NESY", "Russia"), "Jks": ("jks", "Australia"), "HooXi": ("HooXi", "Denmark"),
}

EARNINGS = {
    "S1mple": 2_000_000, "ZywOo": 1_900_000, "NiKo": 1_800_000, "Dev1ce": 2_000_000,
    "Dupreeh": 2_000_000, "Xyp9x": 1_950_000, "Gla1ve": 1_900_000, "Magisk": 1_900_000,
    "Karrigan": 1_700_000, "Rain": 1_700_000, "Ropz": 1_500_000, "Broky": 1_300_000,
    "ElectroNic": 1_600_000, "B1t": 1_300_000, "Perfecto": 1_000_000, "Boombl4": 900_000,
    "ApEX": 1_800_000, "FlameZ": 1_000_000, "Donk": 1_300_000, "Sh1ro": 1_200_000,
    "Chopper": 1_100_000, "Magixx": 1_000_000, "Zont1x": 1_000_000, "Aleksib": 1_000_000,
    "IM": 700_000, "JL": 800_000, "W0nderful": 700_000, "Jame": 1_000_000, "Qikert": 900_000,
    "FL1T": 600_000, "Fame": 500_000, "N0rb3r7": 500_000, "CadiaN": 900_000, "Stavn": 800_000,
    "TeSeS": 700_000, "Sjuush": 700_000, "Refrezh": 600_000, "Skadoodle": 500_000,
    "Stewie2K": 900_000, "Tarik": 600_000, "RUSH": 500_000, "Autimatic": 600_000,
    "Olofmeister": 1_000_000, "GuardiaN": 1_000_000, "Edward": 900_000, "Zeus": 900_000,
    "Flamie": 700_000, "HuNter-": 1_000_000, "Nexa": 700_000, "AmaNEk": 600_000,
    "JaCkz": 700_000, "Allu": 700_000, "Aerial": 400_000, "XseveN": 400_000, "Sergej": 400_000,
    "Twistzz": 1_200_000, "Frozen": 900_000, "Mezii": 500_000, "BLitz": 600_000,
    "Techno4K": 500_000, "Senzu": 500_000, "Mzinho": 500_000, "910": 500_000, "Sdy": 500_000,
    "M0NESY": 1_000_000, "Jks": 900_000, "HooXi": 600_000,
}

REAL_NAMES = {
    "S1mple": "Oleksandr Kostyliev", "ZywOo": "Mathieu Herbaut", "NiKo": "Nikola Kovač",
    "Dev1ce": "Nicolai Reedtz", "Karrigan": "Finn Andersen", "Rain": "Håvard Nygaard",
    "ApEX": "Dan Madesclaire", "ElectroNic": "Denis Sharipov", "Ropz": "Robin Kool",
    "Xyp9x": "Andreas Højsleth", "GuardiaN": "Ladislav Kovács", "Olofmeister": "Olof Kajbjer",
}

R = {
    "NAVI24": ["Aleksib", "IM", "B1t", "JL", "W0nderful"],
    "FAZE24": ["Karrigan", "Rain", "Frozen", "Ropz", "Broky"],
    "SPIRIT24": ["Chopper", "Sh1ro", "Magixx", "Zont1x", "Donk"],
    "VIT25": ["ApEX", "ZywOo", "FlameZ", "Mezii", "Ropz"],
    "MONGOLZ25": ["BLitz", "Techno4K", "Senzu", "Mzinho", "910"],
    "FAZE22": ["Karrigan", "Rain", "Twistzz", "Broky", "Ropz"],
    "NAVI22": ["S1mple", "ElectroNic", "Perfecto", "B1t", "Sdy"],
    "OUT22": ["Jame", "Qikert", "FL1T", "Fame", "N0rb3r7"],
    "HER22": ["CadiaN", "Stavn", "TeSeS", "Sjuush", "Refrezh"],
    "NAVI21": ["S1mple", "ElectroNic", "Boombl4", "Perfecto", "B1t"],
    "G2_21": ["NiKo", "HuNter-", "Nexa", "AmaNEk", "JaCkz"],
    "AST": ["Dev1ce", "Dupreeh", "Xyp9x", "Gla1ve", "Magisk"],
    "ENCE19": ["Allu", "Aerial", "XseveN", "Sergej", "Aleksib"],
    "NAVI18": ["S1mple", "ElectroNic", "Edward", "Zeus", "Flamie"],
    "C9": ["Skadoodle", "Stewie2K", "Tarik", "RUSH", "Autimatic"],
    "FAZE18": ["Karrigan", "Olofmeister", "GuardiaN", "NiKo", "Rain"],
    "G2_23": ["NiKo", "M0NESY", "HuNter-", "Jks", "HooXi"],
}

TEAMS = {  # page key -> (name, template, earnings)
    "Natus_Vincere": ("Natus Vincere", "natus vincere", 9_000_000),
    "FaZe_Clan": ("FaZe Clan", "faze clan", 7_000_000),
    "Team_Spirit": ("Team Spirit", "team spirit", 4_000_000),
    "Team_Vitality": ("Team Vitality", "team vitality", 6_000_000),
    "The_MongolZ": ("The MongolZ", "the mongolz", 1_500_000),
    "Outsiders": ("Outsiders", "outsiders", 1_000_000),
    "Heroic": ("Heroic", "heroic", 2_500_000),
    "G2_Esports": ("G2 Esports", "g2 esports", 5_000_000),
    "Astralis": ("Astralis", "astralis", 8_000_000),
    "ENCE": ("ENCE", "ence", 2_000_000),
    "Cloud9": ("Cloud9", "cloud9", 2_000_000),
}


def _opp(team: str, roster: list[str], flags: dict[str, tuple[str, str]] | None = None) -> dict[str, Any]:
    flags = flags or P
    d: dict[str, Any] = {}
    for i, key in enumerate(roster, 1):
        display, flag = flags[key]
        d[f"p{i}"], d[f"p{i}dn"], d[f"p{i}flag"] = key, display, flag
    return d


def _tournament(page: str, name: str, game: str, tier: str, start: str, end: str,
                organizers: Any, locations: Any, maps: Any, *, publishertier: str = "",
                kind: str = "Offline", prize: float = 1_000_000) -> dict[str, Any]:
    return {
        "pageid": next(_ids), "objectname": "tournament", "pagename": page, "name": name,
        "seriespage": "", "game": game, "type": kind, "organizers": organizers,
        "startdate": start, "enddate": end, "sortdate": end, "locations": locations,
        "prizepool": prize, "liquipediatier": tier, "liquipediatiertype": "",
        "publishertier": publishertier, "maps": maps,
    }


def _placement(page: str, pageid: int, place: str, team: str, roster: list[str], date: str,
               tier: str, flags: dict[str, tuple[str, str]] | None = None) -> dict[str, Any]:
    return {
        "pageid": pageid, "objectname": f"ranking_{place}_{team}", "pagename": page,
        "tournament": page, "parent": page, "placement": place, "date": f"{date} 00:00:00",
        "liquipediatier": tier, "opponentname": team, "opponenttemplate": team.lower(),
        "opponenttype": "team", "opponentplayers": _opp(team, roster, flags),
    }


SYN = {f"Synth{c}": (f"synth{c.lower()}", "Atlantis") for c in "ABCDEFGHIJKLMNO"}


def sample_raw() -> dict[str, list[dict[str, Any]]]:
    pool_cs2_24a = "Ancient;Anubis;Inferno;Mirage;Nuke;Overpass;Vertigo"
    pool_csgo_22 = "Ancient;Dust II;Inferno;Mirage;Nuke;Overpass;Vertigo"
    pool_csgo_18 = "Cache;Dust II;Inferno;Mirage;Nuke;Overpass;Train"
    loc = lambda city, country: {"city1": city, "country1": country}  # noqa: E731

    majors = [
        ("PGL/2024/Copenhagen", "PGL CS2 Major Copenhagen 2024", "cs2", '{"organizer1":"PGL"}',
         "2024-03-17", "2024-03-31", loc("Copenhagen", "dk"), pool_cs2_24a,
         [("1", "Natus Vincere", R["NAVI24"]), ("2", "FaZe Clan", R["FAZE24"])]),
        ("Perfect_World/Major/2024/Shanghai", "Perfect World Shanghai Major 2024", "cs2",
         {"organizer1": "Perfect World"}, "2024-11-30", "2024-12-15", loc("Shanghai", "cn"),
         {"map1": "Ancient", "map2": "Anubis", "map3": "Dust II", "map4": "Inferno",
          "map5": "Mirage", "map6": "Nuke", "map7": "Vertigo"},
         [("1", "Team Spirit", R["SPIRIT24"]), ("2", "FaZe Clan", R["FAZE24"])]),
        ("BLAST/Major/2025/Austin", "BLAST.tv Austin Major 2025", "cs2", "BLAST",
         "2025-06-03", "2025-06-22", json.dumps(loc("Austin", "us")),
         json.dumps(["Ancient", "Anubis", "Dust II", "Inferno", "Mirage", "Nuke", "Train"]),
         [("1", "Team Vitality", R["VIT25"]), ("2", "The MongolZ", R["MONGOLZ25"])]),
        ("PGL/2022/Antwerp", "PGL Major Antwerp 2022", "csgo", '{"organizer1":"PGL"}',
         "2022-05-09", "2022-05-22", loc("Antwerp", "be"), pool_csgo_22,
         [("1", "FaZe Clan", R["FAZE22"]), ("2", "Natus Vincere", R["NAVI22"])]),
        ("IEM/Major/2022/Rio", "IEM Rio Major 2022", "csgo", '{"organizer1":"ESL"}',
         "2022-10-31", "2022-11-13", loc("Rio de Janeiro", "br"), pool_csgo_22,
         [("1", "Outsiders", R["OUT22"]), ("2", "Heroic", R["HER22"])]),
        ("PGL/2021/Stockholm", "PGL Major Stockholm 2021", "csgo", '{"organizer1":"PGL"}',
         "2021-10-26", "2021-11-07", loc("Stockholm", "se"), pool_csgo_22,
         [("1", "Natus Vincere", R["NAVI21"]), ("2", "G2 Esports", R["G2_21"])]),
        ("StarLadder/2019/Berlin", "StarLadder Major Berlin 2019", "csgo", '{"organizer1":"StarLadder"}',
         "2019-08-23", "2019-09-08", loc("Berlin", "de"),
         "Dust II;Inferno;Mirage;Nuke;Overpass;Train;Vertigo",
         [("1", "Astralis", R["AST"])]),
        ("IEM/2019/Katowice", "IEM Katowice Major 2019", "csgo", '{"organizer1":"ESL"}',
         "2019-02-13", "2019-03-03", loc("Katowice", "pl"), pool_csgo_18,
         [("1", "Astralis", R["AST"]), ("2", "ENCE", R["ENCE19"])]),
        ("FACEIT/2018/London", "FACEIT Major: London 2018", "csgo", '{"organizer1":"FACEIT"}',
         "2018-09-05", "2018-09-23", loc("London", "gb"), pool_csgo_18,
         [("1", "Astralis", R["AST"]), ("2", "Natus Vincere", R["NAVI18"])]),
        ("ELEAGUE/2018/Boston", "ELEAGUE Major: Boston 2018", "csgo", '{"organizer1":"ELEAGUE"}',
         "2018-01-12", "2018-01-28", loc("Boston", "us"),
         "Cache;Cobblestone;Inferno;Mirage;Nuke;Overpass;Train",
         [("1", "Cloud9", R["C9"]), ("2", "FaZe Clan", R["FAZE18"])]),
    ]

    tournaments, placements = [], []
    for page, name, game, org, start, end, location, maps, results in majors:
        t = _tournament(page, name, game, "1", start, end, org, location, maps, publishertier="Major Championship")
        tournaments.append(t)
        for place, team, roster in results:
            placements.append(_placement(page, t["pageid"], place, team, roster, end, "1"))

    # A non-Major S-Tier event from before CS2's release.
    t = _tournament("IEM/2023/Katowice", "IEM Katowice 2023", "csgo", "1", "2023-01-31", "2023-02-12",
                    "ESL", loc("Katowice", "pl"), pool_csgo_22)
    tournaments.append(t)
    placements.append(_placement("IEM/2023/Katowice", t["pageid"], "1", "G2 Esports",
                                 R["G2_23"], "2023-02-12", "1"))

    # Synthetic edge cases.
    syn = [
        # Stage sub-page of a Major: its 1st place must not count as a Major win.
        ("PGL/2024/Copenhagen/Opening_Stage", "PGL CS2 Major Copenhagen 2024 - Opening Stage", "cs2", "1",
         "Major Championship", "Synthetic Opening Team", ["SynthA", "SynthB", "SynthC", "SynthD", "SynthE"]),
        # Group-stage page of an S-Tier event: not a title.
        ("Synthetic/2025/Cup/Groups", "Synthetic Cup 2025 - Groups", "cs2", "1", "",
         "Synthetic Stage Team", ["SynthF", "SynthG", "SynthH", "SynthI", "SynthJ"]),
        # Tier-2 event: not S-Tier.
        ("Synthetic/2025/Tier_Two_Cup", "Synthetic Tier Two Cup 2025", "cs2", "2", "",
         "Synthetic Tier2 Team", ["SynthK", "SynthL", "SynthM", "SynthN", "SynthO"]),
    ]
    for page, name, game, tier, pt, team, roster in syn:
        t = _tournament(page, name, game, tier, "2025-01-20", "2025-02-02", "", loc("Atlantis City", "Atlantis"),
                        "", publishertier=pt)
        tournaments.append(t)
        placements.append(_placement(page, t["pageid"], "1", team, roster, "2025-02-02", tier, SYN))
    # A CS 1.6 event: outside the era / game filter.
    t = _tournament("Synthetic/2011/Old_LAN", "Synthetic Old LAN 2011", "cs1", "1", "2011-05-01", "2011-05-03",
                    "", loc("Atlantis City", "Atlantis"), "")
    tournaments.append(t)
    placements.append(_placement(t["pagename"], t["pageid"], "1", "Synthetic Old Team",
                                 ["SynthA", "SynthB", "SynthC", "SynthD", "SynthE"], "2011-05-03", "1", SYN))

    players = []
    for key, (display, flag) in P.items():
        players.append({
            "pageid": next(_ids), "objectname": "player", "pagename": key, "id": display,
            "alternateid": "Techno" if key == "Techno4K" else "", "name": REAL_NAMES.get(key, ""),
            "type": "player", "nationality": flag, "birthdate": "0000-00-00",
            "status": "Active", "earnings": EARNINGS.get(key, 0),
        })

    teams = [{"pageid": next(_ids), "objectname": "team", "pagename": k, "name": n, "template": tpl,
              "earnings": e, "status": "active"} for k, (n, tpl, e) in TEAMS.items()]

    squad = []
    navi = ["S1mple", "ElectroNic", "Boombl4", "Perfecto", "B1t", "Sdy", "Aleksib", "IM", "JL",
            "W0nderful", "Edward", "Zeus", "Flamie", "GuardiaN"]
    for team, roster in (("Natus_Vincere", navi), ("Astralis", R["AST"])):
        pid = next(_ids)
        for key in roster:
            display, flag = P[key]
            squad.append({"pageid": pid, "objectname": f"squad_{key}", "pagename": team, "id": display,
                          "link": key, "name": REAL_NAMES.get(key, ""), "nationality": flag,
                          "role": "", "position": "", "type": "player", "status": "former",
                          "joindate": "2015-01-01", "leavedate": ""})
        squad.append({"pageid": pid, "objectname": "squad_coach", "pagename": team, "id": "Synthetic Coach",
                      "link": "Synthetic_Coach", "role": "Head Coach", "type": "staff", "status": "active"})
        squad.append({"pageid": pid, "objectname": "squad_old", "pagename": team, "id": "Synthetic Oldtimer",
                      "link": "Synthetic_Oldtimer", "type": "player", "status": "former",
                      "joindate": "2008-01-01", "leavedate": "2011-01-01"})

    return {"tournament": tournaments, "placement": placements, "player": players,
            "team": teams, "squadplayer": squad}
