import math
import statistics
from typing import Dict, List, Mapping

from letsquant.indicators import max_drawdown
from letsquant.models import Bar, PortfolioSnapshot


def build_benchmark_metrics(
    bars: List[Bar],
    snapshots: List[PortfolioSnapshot],
    strategy_metrics: Mapping[str, float],
) -> Dict[str, float]:
    if not snapshots:
        return {}

    start_date = snapshots[0].date
    end_date = snapshots[-1].date
    selected = [bar for bar in bars if start_date <= bar.date <= end_date]
    if len(selected) < 2:
        raise ValueError(
            f"benchmark requires at least two bars between {start_date.isoformat()} and {end_date.isoformat()}"
        )

    closes = [bar.close for bar in selected]
    returns = [
        closes[index] / closes[index - 1] - 1
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]
    total_return = closes[-1] / closes[0] - 1
    days = max(1, (selected[-1].date - selected[0].date).days)
    annualized_return = (closes[-1] / closes[0]) ** (365 / days) - 1
    sharpe = 0.0
    if len(returns) > 1 and statistics.pstdev(returns) > 0:
        sharpe = statistics.mean(returns) / statistics.pstdev(returns) * math.sqrt(252)

    return {
        "benchmark_start_close": closes[0],
        "benchmark_final_close": closes[-1],
        "benchmark_total_return": total_return,
        "benchmark_annualized_return": annualized_return,
        "benchmark_max_drawdown": max_drawdown(closes),
        "benchmark_sharpe": sharpe,
        "benchmark_bar_count": float(len(selected)),
        "excess_total_return": float(strategy_metrics.get("total_return", 0.0)) - total_return,
        "excess_annualized_return": float(strategy_metrics.get("annualized_return", 0.0)) - annualized_return,
    }
