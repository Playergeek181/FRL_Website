from frl import timer as t


def test_countdown_and_pause():
    s = t.start(t.new_slot(), now_ms=0)
    assert t.remaining(s, 60_000) == 1_740_000
    s = t.pause(s, 60_000)
    assert t.remaining(s, 999_999) == 1_740_000 and not s["running"]


def test_add_minute_while_running():
    s = t.add(t.start(t.new_slot(), 0), 60_000, 10_000)
    assert t.remaining(s, 10_000) == 1_850_000


def test_tick_stops_at_zero_and_keeps_the_team():
    s = t.tick(t.start(t.new_slot(index=2), 0), 1_800_001)
    assert s == {"index": 2, "running": False, "remaining_ms": 0, "started_at": None}
    assert t.expired(s)


def test_start_does_nothing_once_expired_but_add_gives_time():
    s = t.tick(t.start(t.new_slot(), 0), 1_800_001)
    assert t.start(s, 2_000_000) == s
    s = t.add(s, 60_000, 2_000_000)
    assert not t.expired(s) and t.remaining(s, 2_000_000) == 60_000


def test_reset_keeps_index():
    s = t.reset(t.start(t.new_slot(index=1), 0))
    assert s["index"] == 1 and s["remaining_ms"] == 1_800_000 and not s["running"]


def test_backwards_clock_step_caps_at_remaining():
    s = t.start(t.new_slot(), now_ms=1_000_000)
    assert t.remaining(s, 400_000) == 1_800_000


def test_backwards_clock_step_after_add():
    s = t.add(t.start(t.new_slot(), 0), 60_000, 10_000)
    assert t.remaining(s, 0) == 1_850_000
