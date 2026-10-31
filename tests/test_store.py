import pytest

from frl import timer
from frl.store import Store


def test_restart_keeps_running_timer(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    s.timer_action("start")
    now[0] = 600_000
    s2 = Store(tmp_path, clock=lambda: now[0])
    assert timer.remaining(s2.state["slot"], now[0]) == 1_200_000


def test_delete_current_team_clamps(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b, c = s.add_team("A"), s.add_team("B"), s.add_team("C")
    s.set_order(1, [a["id"], b["id"], c["id"]])
    s.timer_action("next")
    s.timer_action("next")
    s.timer_action("start")
    s.delete_team(b["id"])
    s.delete_team(c["id"])
    slot = s.state["slot"]
    assert slot["index"] == 1 and not slot["running"]
    assert slot["remaining_ms"] == 1_800_000
    assert s.current_and_next() == (None, None)


def test_past_end_slot_does_not_keep_advancing(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    s.timer_action("next")
    s.timer_action("start")
    assert not s.state["slot"]["running"]
    now[0] = 10 * 1_800_000
    assert s.current_and_next() == (None, None)
    assert s.state["slot"]["index"] == 1
    s.set_order(1, [a["id"], s.add_team("B")["id"]])
    assert s.state["slot"]["index"] == 1 and not s.state["slot"]["running"]


def test_shrinking_order_clamps_index(tmp_path):
    s = Store(tmp_path)
    ids = [s.add_team(n)["id"] for n in "ABC"]
    s.set_order(1, ids)
    s.timer_action("next")
    s.timer_action("next")
    s.set_order(1, ids[:1])
    assert s.state["slot"]["index"] == 1


def test_delete_team_cascades(tmp_path):
    s = Store(tmp_path)
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(2, [a["id"], b["id"]])
    s.add_attempt(a["id"], 1, dict(bases=1, repeats=0, returned=False, open_hw=False))
    s.delete_team(a["id"])
    assert s.state["orders"]["2"] == [b["id"]]
    assert s.state["attempts"] == []
    with pytest.raises(KeyError):
        s.delete_team(a["id"])


def test_update_and_delete_attempt(tmp_path):
    s = Store(tmp_path)
    a = s.add_team("A")
    at = s.add_attempt(a["id"], 1, dict(bases=2, repeats=0, returned=False, open_hw=False))
    at2 = s.update_attempt(at["id"], dict(bases=4, repeats=0, returned=False, open_hw=False))
    assert at2["points"] == 80 and s.best_by_phase()[1][a["id"]] == 80
    with pytest.raises(ValueError):
        s.update_attempt(at["id"], dict(bases=99, repeats=0, returned=False, open_hw=False))
    s.delete_attempt(at["id"])
    assert s.best_by_phase()[1][a["id"]] is None
    with pytest.raises(KeyError):
        s.delete_attempt(at["id"])
    with pytest.raises(KeyError):
        s.update_attempt("nope", {})


def test_set_phase_validates_and_resets_slot(tmp_path):
    s = Store(tmp_path)
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    s.timer_action("start")
    s.set_phase(3)
    assert s.state["active_phase"] == 3
    assert s.state["slot"] == timer.new_slot(0)
    for bad in (0, 5):
        with pytest.raises(ValueError):
            s.set_phase(bad)


def test_timer_actions_via_store(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    s.timer_action("start")
    now[0] = 60_000
    s.timer_action("pause")
    assert s.state["slot"]["remaining_ms"] == 1_740_000
    s.timer_action("add")
    assert s.state["slot"]["remaining_ms"] == 1_800_000
    s.timer_action("add", now_ms=5)
    assert s.state["slot"]["remaining_ms"] == 1_860_000
    s.timer_action("reset")
    assert s.state["slot"] == timer.new_slot(0)
    with pytest.raises(ValueError):
        s.timer_action("bogus")


def test_set_order_unknown_team(tmp_path):
    s = Store(tmp_path)
    with pytest.raises(KeyError):
        s.set_order(1, ["nope"])


def test_auto_advance_shows_next(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.timer_action("start")
    now[0] = 1_800_001
    cur, nxt = s.current_and_next()
    assert cur["id"] == b["id"] and nxt is None and not s.state["slot"]["running"]


def test_fourth_attempt_rejected(tmp_path):
    s = Store(tmp_path)
    a = s.add_team("A")
    inp = dict(bases=1, repeats=0, returned=False, open_hw=False)
    for _ in range(3):
        s.add_attempt(a["id"], 1, inp)
    with pytest.raises(ValueError):
        s.add_attempt(a["id"], 1, inp)


def test_best_by_phase(tmp_path):
    s = Store(tmp_path)
    a = s.add_team("A")
    b = s.add_team("B")
    s.add_attempt(a["id"], 1, dict(bases=2, repeats=0, returned=False, open_hw=False))
    s.add_attempt(a["id"], 1, dict(bases=4, repeats=0, returned=False, open_hw=False))
    assert s.best_by_phase()[1] == {a["id"]: 80, b["id"]: None}


def test_missing_file_starts_empty_and_write_is_atomic(tmp_path):
    s = Store(tmp_path)
    s.add_team("A")
    assert (tmp_path / "state.json").exists() and not (tmp_path / "state.json.tmp").exists()
    assert Store(tmp_path).state["teams"][0]["name"] == "A"
