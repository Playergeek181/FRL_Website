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
    s = Store(tmp_path)
    a = s.add_team("A")
    b = s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.timer_action("next")
    s.delete_team(b["id"])
    assert s.current_and_next() == (None, None)


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
