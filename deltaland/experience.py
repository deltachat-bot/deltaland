"""Player experience and level logic"""


def lvl2exp(lvl: int) -> float:
    return 4 * lvl**3 / 5


def required_exp(lvl: int) -> int:
    assert lvl > 1
    return round(lvl2exp(lvl) - lvl2exp(lvl - 1))
