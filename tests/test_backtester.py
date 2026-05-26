import unittest
from datetime import date, timedelta
from typing import List

from letsquant.config import CostConfig, RiskConfig
from letsquant.execution import Backtester
from letsquant.models import Action, Bar
from letsquant.strategies import TrendBreakoutStrategy


def synthetic_bars() -> List[Bar]:
    bars = []
    start = date(2024, 1, 1)
    closes = [10 + index * 0.03 for index in range(24)]
    closes += [11.2, 11.4, 11.6, 11.8, 12.0, 12.2, 12.4]
    closes += [12.1, 11.7, 11.2, 10.8, 10.4, 10.1]
    for index, close in enumerate(closes):
        bars.append(
            Bar(
                symbol="000001.SZ",
                date=start + timedelta(days=index),
                open=close,
                high=close + 0.08,
                low=close - 0.08,
                close=close,
                volume=1000000 + index * 1000,
            )
        )
    return bars


class BacktesterTests(unittest.TestCase):
    def test_backtester_executes_breakout_trade(self) -> None:
        strategy = TrendBreakoutStrategy(
            short_window=5,
            mid_window=10,
            long_window=20,
            breakout_window=10,
            momentum_window=10,
            min_momentum=0.02,
            volume_window=10,
            min_volume_ratio=0.8,
            stop_loss_pct=0.08,
            trailing_stop_pct=0.12,
            max_holding_days=45,
        )
        backtester = Backtester(
            strategy=strategy,
            initial_cash=100000,
            risk=RiskConfig(max_position_pct=0.2, max_positions=5, cash_reserve_pct=0.05),
            costs=CostConfig(slippage_bps=0),
        )
        result = backtester.run({"000001.SZ": synthetic_bars()})

        self.assertGreaterEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].action, Action.BUY)
        self.assertEqual(result.trades[0].shares % 100, 0)
        self.assertIn("total_return", result.metrics)


if __name__ == "__main__":
    unittest.main()
