from frl.ranking import phase_ranking, overall_ranking

def test_phase_ties_skip_positions():
    r = phase_ranking({"a": 100, "b": 100, "c": 50})
    assert r["a"] == {"position": 1, "points": 25}
    assert r["b"] == {"position": 1, "points": 25}
    assert r["c"] == {"position": 3, "points": 15}

def test_eleventh_gets_zero():
    best = {f"t{i}": 200 - i for i in range(11)}
    r = phase_ranking(best)
    assert r["t9"]["points"] == 1
    assert r["t10"] == {"position": 11, "points": 0}

def test_zero_and_absent_unranked():
    r = phase_ranking({"a": 0, "b": None, "c": 10})
    assert r["a"] == {"position": None, "points": 0}
    assert r["b"] == {"position": None, "points": 0}
    assert r["c"] == {"position": 1, "points": 25}

def test_overall_tiebreak_more_phases_wins():
    best = {
        1: {"A": 300, "X": 250, "B": 200, "Y": 150, "Z": 100},
        2: {"Y": 300, "Z": 250, "X": 200, "C": 150, "B": 100},
        3: {}, 4: {},
    }
    rows = overall_ranking(["A", "B", "C", "X", "Y", "Z"], best)
    by = {r["team_id"]: r for r in rows}
    assert by["A"]["total"] == 25 and by["B"]["total"] == 25
    assert by["B"]["position"] < by["A"]["position"]
    assert by["A"]["phase_points"][2] is None
    assert by["B"]["phases_scored"] == 2

def test_overall_tiebreak_phase1_score():
    best = {1: {"A": 100, "B": 90}, 2: {"B": 100, "A": 90}, 3: {}, 4: {}}
    rows = overall_ranking(["B", "A"], best)
    assert [r["team_id"] for r in rows] == ["A", "B"]
    assert rows[0]["position"] == 1 and rows[1]["position"] == 2

def test_overall_full_tie_shares_position():
    best = {1: {"A": 100, "B": 100}, 2: {}, 3: {}, 4: {}}
    rows = overall_ranking(["A", "B"], best)
    assert rows[0]["position"] == rows[1]["position"] == 1

def test_team_with_nothing_is_last():
    best = {1: {"A": 10}, 2: {}, 3: {}, 4: {}}
    rows = overall_ranking(["Z", "A"], best)
    assert rows[-1]["team_id"] == "Z" and rows[-1]["total"] == 0

def test_zero_total_teams_have_no_position():
    rows = overall_ranking(["A", "B", "C"], {1: {}, 2: {}, 3: {}, 4: {}})
    assert [r["position"] for r in rows] == [None, None, None]
    assert [r["team_id"] for r in rows] == ["A", "B", "C"]

def test_only_scored_teams_get_position():
    best = {1: {"A": None, "B": 40, "C": 0}, 2: {}, 3: {}, 4: {}}
    rows = overall_ranking(["A", "B", "C"], best)
    by = {r["team_id"]: r for r in rows}
    assert rows[0]["team_id"] == "B" and by["B"]["position"] == 1
    assert by["A"]["position"] is None and by["C"]["position"] is None
