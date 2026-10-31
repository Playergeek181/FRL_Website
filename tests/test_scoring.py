import pytest
from frl.scoring import attempt_points, validate_attempt

@pytest.mark.parametrize("phase,inputs,expected", [
    (1, dict(bases=5, repeats=1, returned=True, open_hw=True), 380),
    (1, dict(bases=6, repeats=0, returned=True, open_hw=True), 480),
    (1, dict(bases=3, repeats=0, returned=False, open_hw=False), 60),
    (1, dict(bases=0, repeats=2, returned=True, open_hw=True), 0),      # negative → 0, no doubling
    (2, dict(lifted=3, delivered=3, dropped=0, returned=True, open_hw=True), 720),
    (2, dict(lifted=2, delivered=0, dropped=1, returned=True, open_hw=False), 75),  # no delivery → no return bonus
    (2, dict(lifted=2, delivered=1, dropped=0, returned=True, open_hw=False), 200),
    (3, dict(recognized=False, bases=6, repeats=0, cross_repeats=0, returned=True, open_hw=True), 0),
    (3, dict(recognized=True, bases=6, repeats=0, cross_repeats=0, returned=True, open_hw=True), 480),
    (3, dict(recognized=True, bases=4, repeats=1, cross_repeats=1, returned=False, open_hw=False), 65),
    (3, dict(recognized=True, bases=0, repeats=0, cross_repeats=0, returned=True, open_hw=False), 0),
    (4, dict(maze=True, qr=5, landed=True, open_hw=True), 600),
    (4, dict(maze=False, qr=2, landed=True, open_hw=False), 40),         # did not exit maze → no doubling
    (4, dict(maze=True, qr=0, landed=True, open_hw=False), 50),          # no QR → no doubling
])
def test_attempt_points(phase, inputs, expected):
    assert attempt_points(phase, inputs) == expected

def test_validate_rejects_out_of_range():
    assert validate_attempt(1, dict(bases=7, repeats=0, returned=False, open_hw=False))
    assert validate_attempt(2, dict(lifted=1, delivered=2, dropped=0, returned=False, open_hw=False))
    assert validate_attempt(2, dict(lifted=2, delivered=1, dropped=2, returned=False, open_hw=False))
    assert validate_attempt(4, dict(maze=True, qr=6, landed=False, open_hw=False))
    assert validate_attempt(1, dict(bases=-1, repeats=0, returned=False, open_hw=False))
    assert validate_attempt(5, {})                                       # unknown phase

def test_validate_accepts_valid():
    assert validate_attempt(1, dict(bases=6, repeats=3, returned=True, open_hw=False)) == []
