from typing import Iterable, Optional, Sequence


def sma(values: Sequence[float], window: int) -> Optional[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def rate_of_change(values: Sequence[float], window: int) -> Optional[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) <= window:
        return None
    base = values[-window - 1]
    if base == 0:
        return None
    return values[-1] / base - 1


def max_drawdown(equity_values: Iterable[float]) -> float:
    peak = None
    worst = 0.0
    for value in equity_values:
        if peak is None or value > peak:
            peak = value
        if peak and peak > 0:
            dd = value / peak - 1
            if dd < worst:
                worst = dd
    return worst
