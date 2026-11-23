import json
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
    for bad in (-1, 5):
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
    slot = dict(s.state["slot"])
    assert slot.pop("prev")["remaining_ms"] == 1_860_000   # guardado para "Desfazer"
    assert slot == timer.new_slot(0)
    with pytest.raises(ValueError):
        s.timer_action("bogus")


def test_set_order_unknown_team(tmp_path):
    s = Store(tmp_path)
    with pytest.raises(KeyError):
        s.set_order(1, ["nope"])


def test_time_up_keeps_team_in_arena_until_next(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.timer_action("start")
    now[0] = 1_800_001
    cur, nxt = s.current_and_next()
    assert cur["id"] == a["id"] and nxt["id"] == b["id"]
    assert timer.expired(s.state["slot"])
    assert timer.expired(Store(tmp_path).state["slot"])   # sobrevive a reinício/queda de energia
    s.timer_action("next")
    assert s.current_and_next()[0]["id"] == b["id"]
    assert s.state["slot"]["remaining_ms"] == 1_800_000


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


def test_corrupt_state_loads_backup_and_moves_bad_file_aside(tmp_path):
    s = Store(tmp_path)
    s.add_team("A")
    s.add_team("B")          # second save: .bak holds the state with team A
    assert (tmp_path / "state.json.bak").exists()
    (tmp_path / "state.json").write_text("{corrupt", encoding="utf-8")
    s2 = Store(tmp_path)
    assert [t["name"] for t in s2.state["teams"]] == ["A"]
    aside = list(tmp_path.glob("state.json.corrupt-*"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == "{corrupt"
    s2.add_team("C")         # keeps working and persisting afterwards
    assert [t["name"] for t in Store(tmp_path).state["teams"]] == ["A", "C"]


def test_corrupt_state_without_backup_starts_empty_and_preserves_file(tmp_path):
    (tmp_path / "state.json").write_text("garbage", encoding="utf-8")
    s = Store(tmp_path)
    assert s.state["teams"] == [] and s.state["active_phase"] == 1
    aside = list(tmp_path.glob("state.json.corrupt-*"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == "garbage"


def test_save_keeps_previous_good_file_as_bak(tmp_path):
    s = Store(tmp_path)
    s.add_team("A")
    s.add_team("B")
    bak = json.loads((tmp_path / "state.json.bak").read_text(encoding="utf-8"))
    assert [t["name"] for t in bak["teams"]] == ["A"]


def test_pause_after_expiry_stays_time_up(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.timer_action("start")
    now[0] = 1_800_001
    s.timer_action("pause")
    slot = s.state["slot"]
    assert slot["index"] == 0 and not slot["running"] and slot["remaining_ms"] == 0
    s.timer_action("start")                     # Iniciar em 00:00 não faz nada
    assert timer.expired(s.state["slot"])
    s.timer_action("add")                       # +1 min dá tempo extra à mesma equipe
    assert s.state["slot"]["remaining_ms"] == 60_000 and s.state["slot"]["index"] == 0


def test_delete_earlier_team_keeps_current_team(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b, c = s.add_team("A"), s.add_team("B"), s.add_team("C")
    s.set_order(1, [a["id"], b["id"], c["id"]])
    s.timer_action("next")
    s.timer_action("start")
    now[0] = 100_000
    s.delete_team(a["id"])
    slot = s.state["slot"]
    assert slot["index"] == 0 and slot["running"] and slot["started_at"] == 0
    assert s.current_and_next()[0]["id"] == b["id"]
    assert timer.remaining(slot, now[0]) == 1_700_000


def test_reorder_keeps_current_team(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b, c = s.add_team("A"), s.add_team("B"), s.add_team("C")
    s.set_order(1, [a["id"], b["id"], c["id"]])
    s.timer_action("next")
    s.timer_action("start")
    s.set_order(1, [b["id"], c["id"], a["id"]])
    assert s.state["slot"]["index"] == 0 and s.state["slot"]["running"]
    s.set_order(1, [c["id"], a["id"], b["id"]])
    assert s.state["slot"]["index"] == 2 and s.state["slot"]["running"]
    assert s.current_and_next()[0]["id"] == b["id"]


def test_order_change_in_inactive_phase_does_not_move_slot(tmp_path):
    s = Store(tmp_path)
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.timer_action("next")
    s.set_order(2, [b["id"], a["id"]])
    assert s.state["slot"]["index"] == 1


def test_next_right_after_expiry_does_not_skip_a_team(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    ids = [s.add_team(n)["id"] for n in "ABC"]
    s.set_order(1, ids)
    s.timer_action("start")
    now[0] = 1_800_001
    s.timer_action("next")      # 00:00 keeps A; next moves exactly one step, to B
    assert s.state["slot"]["index"] == 1


# -- backups de pontuação ---------------------------------------------
P1 = dict(bases=2, repeats=0, returned=False, open_hw=False)


def _backups(tmp_path):
    d = tmp_path / "backups"
    return sorted(d.glob("*.json")) if d.exists() else []


def test_each_score_change_writes_a_backup(tmp_path):
    s = Store(tmp_path, clock=lambda: 1_793_600_000_000)
    a = s.add_team("Capybots")
    s.set_order(1, [a["id"]])
    assert _backups(tmp_path) == []          # equipes/ordem não geram backup
    at = s.add_attempt(a["id"], 1, P1)
    s.update_attempt(at["id"], dict(P1, bases=3))
    s.delete_attempt(at["id"])
    files = _backups(tmp_path)
    assert len(files) == 3
    names = [f.name for f in files]
    assert any("salva" in n for n in names)
    assert any("editada" in n for n in names)
    assert any("excluida" in n for n in names)
    assert all("capybots" in n for n in names)


def test_backup_is_a_restorable_state(tmp_path):
    s = Store(tmp_path, clock=lambda: 1_793_600_000_000)
    a = s.add_team("A")
    s.add_attempt(a["id"], 1, P1)
    backup = _backups(tmp_path)[-1]
    data = json.loads(backup.read_text(encoding="utf-8"))
    assert data["attempts"][0]["points"] == 40
    # restaurar = copiar o backup por cima de state.json
    (tmp_path / "state.json").write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "state.json.bak").unlink()
    assert Store(tmp_path).state["attempts"][0]["points"] == 40


def test_backups_never_overwrite_each_other(tmp_path):
    s = Store(tmp_path, clock=lambda: 1_793_600_000_000)   # mesmo instante
    a = s.add_team("A")
    for _ in range(3):
        s.add_attempt(a["id"], 1, P1)
    assert len(_backups(tmp_path)) == 3


def test_backup_failure_does_not_lose_the_score(tmp_path, capsys):
    s = Store(tmp_path, clock=lambda: 1_793_600_000_000)
    a = s.add_team("A")
    (tmp_path / "backups").write_text("não é uma pasta")    # força erro ao gravar backup
    s.add_attempt(a["id"], 1, P1)
    assert Store(tmp_path).state["attempts"][0]["points"] == 40
    assert "backup" in capsys.readouterr().err


def test_deleting_a_team_with_scores_backs_them_up_first(tmp_path):
    s = Store(tmp_path, clock=lambda: 1_793_600_000_000)
    a, b = s.add_team("RobôCin"), s.add_team("Sem pontos")
    s.add_attempt(a["id"], 1, P1)
    s.delete_team(b["id"])                      # sem tentativas: nenhum backup novo
    assert len(_backups(tmp_path)) == 1
    s.delete_team(a["id"])
    last = [f for f in _backups(tmp_path) if "excluir-equipe" in f.name]
    assert len(last) == 1 and "robocin" in last[0].name
    data = json.loads(last[0].read_text(encoding="utf-8"))
    assert data["attempts"][0]["points"] == 40   # o backup ainda tem a pontuação


# -- desfazer exclusão de equipe ----------------------------------------
def test_restore_team_brings_back_scores_and_order(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b, c = s.add_team("A"), s.add_team("B"), s.add_team("C")
    s.set_order(1, [a["id"], b["id"], c["id"]])
    s.set_order(2, [b["id"], c["id"]])
    s.add_attempt(b["id"], 1, P1)
    s.add_attempt(a["id"], 1, P1)
    s.timer_action("next")
    s.timer_action("next")                  # C na arena
    s.timer_action("start")
    before = json.loads(json.dumps(s.state))
    s.delete_team(b["id"])
    assert s.current_and_next()[0]["id"] == c["id"]
    s.restore_team(b["id"])
    assert s.state["teams"] == before["teams"]
    assert s.state["orders"] == before["orders"]
    assert s.state["attempts"] == before["attempts"]
    assert s.state["slot"]["index"] == 2 and s.state["slot"]["running"]
    with pytest.raises(ValueError):
        s.restore_team(b["id"])             # só uma vez


def test_restore_only_the_last_deleted_team(tmp_path):
    s = Store(tmp_path)
    a, b = s.add_team("A"), s.add_team("B")
    s.delete_team(a["id"])
    s.delete_team(b["id"])
    with pytest.raises(ValueError):
        s.restore_team(a["id"])
    s.restore_team(b["id"])
    assert [t["name"] for t in s.state["teams"]] == ["B"]


UNDO_P1 = {"bases": 3, "repeats": 0, "returned": True, "open_hw": False}


def test_next_can_be_undone_with_time_kept_and_paused(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.timer_action("start")
    now[0] = 600_000
    s.timer_action("next")
    assert s.current_and_next()[0]["id"] == b["id"]
    now[0] = 605_000
    s.timer_action("back")
    slot = s.state["slot"]
    assert s.current_and_next()[0]["id"] == a["id"]
    assert not slot["running"] and timer.remaining(slot, now[0]) == 1_200_000
    with pytest.raises(ValueError):   # só um passo para trás
        s.timer_action("back")


def test_back_without_next_is_refused(tmp_path):
    s = Store(tmp_path, clock=lambda: 0)
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    with pytest.raises(ValueError):
        s.timer_action("back")


def test_restored_attempt_keeps_its_place_and_id(tmp_path):
    s = Store(tmp_path, clock=lambda: 0)
    a = s.add_team("A")
    t1 = s.add_attempt(a["id"], 1, UNDO_P1)
    t2 = s.add_attempt(a["id"], 1, {**UNDO_P1, "bases": 5})
    s.delete_attempt(t1["id"])
    s.restore_attempt(t1["id"])
    assert [x["id"] for x in s.state["attempts"]] == [t1["id"], t2["id"]]
    with pytest.raises(ValueError):   # o mesmo desfazer não vale duas vezes
        s.restore_attempt(t1["id"])


def test_restore_attempt_respects_three_attempt_limit(tmp_path):
    s = Store(tmp_path, clock=lambda: 0)
    a = s.add_team("A")
    t1 = s.add_attempt(a["id"], 1, UNDO_P1)
    s.add_attempt(a["id"], 1, UNDO_P1)
    s.delete_attempt(t1["id"])
    s.add_attempt(a["id"], 1, UNDO_P1)
    s.add_attempt(a["id"], 1, UNDO_P1)
    with pytest.raises(ValueError):
        s.restore_attempt(t1["id"])


def test_minus_one_minute_never_goes_below_zero(tmp_path):
    s = Store(tmp_path, clock=lambda: 0)
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    s.timer_action("add")
    s.timer_action("sub")
    assert timer.remaining(s.state["slot"], 0) == 1_800_000
    s.state["slot"]["remaining_ms"] = 20_000
    s.timer_action("sub")
    assert timer.remaining(s.state["slot"], 0) == 0


def test_reset_can_be_undone(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a = s.add_team("A")
    s.set_order(1, [a["id"]])
    s.timer_action("start")
    now[0] = 300_000
    s.timer_action("reset")
    assert timer.remaining(s.state["slot"], now[0]) == 1_800_000
    s.timer_action("back")
    slot = s.state["slot"]
    assert not slot["running"] and timer.remaining(slot, now[0]) == 1_500_000


def test_phase_change_can_be_undone(tmp_path):
    now = [0]
    s = Store(tmp_path, clock=lambda: now[0])
    a, b = s.add_team("A"), s.add_team("B")
    s.set_order(1, [a["id"], b["id"]])
    s.set_order(2, [b["id"], a["id"]])
    s.timer_action("next")
    s.timer_action("start")
    now[0] = 60_000
    s.set_phase(2)
    assert s.state["active_phase"] == 2 and s.current_and_next()[0]["id"] == b["id"]
    s.undo_phase()
    slot = s.state["slot"]
    assert s.state["active_phase"] == 1 and slot["index"] == 1
    assert not slot["running"] and timer.remaining(slot, now[0]) == 1_740_000
    with pytest.raises(ValueError):
        s.undo_phase()
