from typing import Any, Dict

from letsquant.strategies.base import Strategy
from letsquant.strategies.trend_breakout import TrendBreakoutStrategy


def build_strategy(name: str, params: Dict[str, Any]) -> Strategy:
    if name == "trend_breakout":
        return TrendBreakoutStrategy(**params)
    raise ValueError(f"unknown strategy: {name}")
