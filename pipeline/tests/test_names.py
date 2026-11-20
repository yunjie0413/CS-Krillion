from cskrill.names import Matcher, max_edits, norm, osa_distance, team_name_variants


def test_norm_strips_case_accents_and_symbols():
    assert norm("Håvard Nygaard") == "havardnygaard"
    assert norm("Nikola Kovač") == "nikolakovac"
    assert norm("Andreas Højsleth") == "andreashojsleth"
    assert norm("huNter-") == "hunter"
    assert norm("Na'Vi") == "navi"
    assert norm("de_dust2") == "dedust2"


def test_team_variants_drop_affixes():
    assert "Vitality" in team_name_variants("Team Vitality")
    assert "FaZe" in team_name_variants("FaZe Clan")
    assert team_name_variants("Astralis") == {"Astralis"}


def test_osa_distance_and_cutoff():
    assert osa_distance("zywoo", "zywoo", 2) == 0
    assert osa_distance("zywoo", "zywo", 2) == 1
    assert osa_distance("dveice", "device", 2) == 1  # adjacent swap
    assert osa_distance("abcdef", "uvwxyz", 2) == 3  # stops early at cutoff + 1
    assert [max_edits(n) for n in (3, 5, 9)] == [0, 1, 2]


UNIVERSE = {
    "S1mple": {"s1mple", "Oleksandr Kostyliev"},
    "ZywOo": {"ZywOo", "Mathieu Herbaut"},
    "Dev1ce": {"dev1ce"},
    "Device_(Swedish_player)": {"device"},  # homonym once leet-folded
    "NiKo": {"NiKo"},
    "Nikko": {"nikko"},
}


def test_exact_leet_and_real_name():
    m = Matcher.from_universe(UNIVERSE)
    assert m.lookup("S1MPLE")[0] == {"S1mple"}
    assert m.lookup("simple") == (frozenset({"S1mple"}), "leet")
    assert m.lookup("oleksandr kostyliev")[0] == {"S1mple"}


def test_fuzzy_needs_a_unique_target():
    m = Matcher.from_universe(UNIVERSE)
    assert m.lookup("zywooo") == (frozenset({"ZywOo"}), "fuzzy")
    # 'niko' and 'nikko' are both one edit away: ambiguous, so no match
    assert m.lookup("nikoo")[0] == set()
    assert m.lookup("nkko")[0] == set()
    assert Matcher.from_universe(UNIVERSE, fuzzy=False).lookup("zywooo")[0] == set()


def test_judge_correct_wrong_unknown_and_homonyms():
    m = Matcher.from_universe(UNIVERSE)
    answers = {"S1mple", "Dev1ce"}
    assert m.judge("s1mple", answers).status == "correct"
    assert m.judge("NiKo", answers).status == "wrong"
    assert m.judge("qwertyuiop", answers).status == "unknown"
    # "device" leet-folds to both device players; only one is a valid answer
    v = m.judge("device", answers)
    assert (v.status, v.key) == ("correct", "Dev1ce")
    both = {"Dev1ce", "Device_(Swedish_player)"}
    assert m.judge("device", both, rank={"Dev1ce": 0.2, "Device_(Swedish_player)": 0.01}).key == "Dev1ce"
