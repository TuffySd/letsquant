import unittest
from datetime import date, timedelta
from typing import List, Optional

from letsquant.config import CostConfig, RiskConfig
from letsquant.execution import Backtester
from letsquant.models import Action, Bar, Position, Signal
from letsquant.strategies.base import Strategy
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


class ScriptedStrategy(Strategy):
    def generate(
        self,
        symbol: str,
        history: List[Bar],
        position: Optional[Position],
    ) -> Signal:
        if len(history) == 1 and position is None:
            return Signal(history[-1].date, symbol, Action.BUY, "scripted buy", reference_price=history[-1].close)
        if len(history) == 2 and position is not None:
            return Signal(history[-1].date, symbol, Action.SELL, "scripted sell", reference_price=history[-1].close)
        return Signal(history[-1].date, symbol, Action.HOLD, "hold", reference_price=history[-1].close)


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

    def test_backtester_rejects_buy_when_next_open_is_limit_up(self) -> None:
        bars = [
            Bar("000001.SZ", date(2024, 1, 2), 10, 10.2, 9.8, 10),
            Bar("000001.SZ", date(2024, 1, 3), 11, 11, 10.8, 11, limit_up=11),
        ]
        backtester = Backtester(
            strategy=ScriptedStrategy(),
            initial_cash=100000,
            risk=RiskConfig(max_position_pct=0.2, max_positions=5, cash_reserve_pct=0.05),
            costs=CostConfig(slippage_bps=0),
        )
        result = backtester.run({"000001.SZ": bars})

        self.assertEqual(result.trades, [])
        self.assertEqual(len(result.order_rejections), 1)
        self.assertEqual(result.order_rejections[0].reason, "limit_up")
        self.assertEqual(result.metrics["order_rejection_count"], 1.0)

    def test_backtester_rejects_sell_when_next_open_is_limit_down(self) -> None:
        bars = [
            Bar("000001.SZ", date(2024, 1, 2), 10, 10.2, 9.8, 10),
            Bar("000001.SZ", date(2024, 1, 3), 10.1, 10.3, 10, 10.2),
            Bar("000001.SZ", date(2024, 1, 4), 9.2, 9.4, 9.2, 9.3, limit_down=9.2),
        ]
        backtester = Backtester(
            strategy=ScriptedStrategy(),
            initial_cash=100000,
            risk=RiskConfig(max_position_pct=0.2, max_positions=5, cash_reserve_pct=0.05),
            costs=CostConfig(slippage_bps=0),
        )
        result = backtester.run({"000001.SZ": bars})

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].action, Action.BUY)
        self.assertEqual(len(result.order_rejections), 1)
        self.assertEqual(result.order_rejections[0].action, Action.SELL)
        self.assertEqual(result.order_rejections[0].reason, "limit_down")


if __name__ == "__main__":
    unittest.main()
