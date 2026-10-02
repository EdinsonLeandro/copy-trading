import random

import pytest

from src.common.config import get_long_tail_delay_ms


class FakeRng:
    """Returns a fixed `random()` roll so each tier can be hit deliberately;
    `randint` is real so the result still lands somewhere in the tier."""

    def __init__(self, roll: float):
        self.roll = roll
        self._rng = random.Random(0)

    def random(self) -> float:
        return self.roll

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)


@pytest.mark.parametrize(
    "roll, low, high",
    [
        (0.0, 300, 800),        # short tier: plain min-max
        (0.69, 300, 800),
        (0.70, 2400, 8000),     # medium tier: 3-10x max
        (0.92, 2400, 8000),
        (0.93, 12000, 36000),   # long tier: 15-45x max
        (0.999, 12000, 36000),
    ],
)
def test_long_tail_delay_tiers(roll, low, high):
    delay = get_long_tail_delay_ms(300, 800, rng=FakeRng(roll))
    assert low <= delay <= high


def test_long_tail_delay_accepts_swapped_bounds():
    delay = get_long_tail_delay_ms(800, 300, rng=FakeRng(0.0))
    assert 300 <= delay <= 800


def test_long_tail_delay_is_mostly_short_but_sometimes_long():
    rng = random.Random(42)
    delays = [get_long_tail_delay_ms(300, 800, rng=rng) for _ in range(5000)]
    short_share = sum(d <= 800 for d in delays) / len(delays)
    assert 0.65 < short_share < 0.75
    assert max(delays) >= 12000
