import unittest
from datetime import date

from letsquant.config import CostConfig, RiskConfig
from letsquant.execution.instructions import build_manual_orders
from letsquant.models import Action, Bar, Signal


class InstructionTests(unittest.TestCase):
    def test_buy_order_rounds_to_a_share_lot_size(self) -> None:
        bars = [
            Bar(
                symbol="000001.SZ",
                date=date(2024, 1, 2),
                open=10,
                high=10.2,
                low=9.8,
                close=10,
                volume=1000000,
            )
        ]
        signals = [Signal(date(2024, 1, 2), "000001.SZ", Action.BUY, "entry", 1, 10)]
        orders = build_manual_orders(
            signals,
            {"000001.SZ": bars},
            cash=100000,
            positions={},
            risk=RiskConfig(max_position_pct=0.2, lot_size=100),
            costs=CostConfig(slippage_bps=0),
        )

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].shares, 2000)


if __name__ == "__main__":
    unittest.main()
