from frl import timer as t


def test_countdown_and_pause():
    s = t.start(t.new_slot(), now_ms=0)
    assert t.remaining(s, 60_000) == 1_740_000
    s = t.pause(s, 60_000)
    assert t.remaining(s, 999_999) == 1_740_000 and not s["running"]


def test_add_minute_while_running():
    s = t.add(t.start(t.new_slot(), 0), 60_000, 10_000)
    assert t.remaining(s, 10_000) == 1_850_000


def test_tick_auto_advances_and_waits():
    s = t.tick(t.start(t.new_slot(index=2), 0), 1_800_001)
    assert s == {"index": 3, "running": False, "remaining_ms": 1_800_000, "started_at": None}


def test_reset_keeps_index():
    s = t.reset(t.start(t.new_slot(index=1), 0))
    assert s["index"] == 1 and s["remaining_ms"] == 1_800_000 and not s["running"]
