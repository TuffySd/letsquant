import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from letsquant.execution.fills import Fill, reconcile_fills, write_fill_reconciliation
from letsquant.models import Action, ManualOrder


class FillReconciliationTests(unittest.TestCase):
    def test_reconciles_filled_partial_and_unplanned_fills(self) -> None:
        orders = [
            ManualOrder(date(2024, 1, 2), "000001.SZ", Action.BUY, 1000, 10.0, 10000, "entry", ""),
            ManualOrder(date(2024, 1, 2), "600000.SH", Action.SELL, 800, 8.0, 6400, "exit", ""),
        ]
        fills = [
            Fill(date(2024, 1, 3), date(2024, 1, 2), "000001.SZ", Action.BUY, 600, 10.1, commission=5),
            Fill(date(2024, 1, 3), date(2024, 1, 2), "300001.SZ", Action.BUY, 100, 20.0, note="manual extra"),
        ]

        rows = reconcile_fills(orders, fills)

        by_symbol = {row.symbol: row for row in rows}
        self.assertEqual(by_symbol["000001.SZ"].status, "partial")
        self.assertEqual(by_symbol["000001.SZ"].filled_shares, 600)
        self.assertEqual(by_symbol["000001.SZ"].share_diff, -400)
        self.assertAlmostEqual(by_symbol["000001.SZ"].slippage_bps, 100)
        self.assertEqual(by_symbol["600000.SH"].status, "not_filled")
        self.assertEqual(by_symbol["300001.SZ"].status, "unplanned")
        self.assertEqual(by_symbol["300001.SZ"].planned_shares, 0)

    def test_sell_slippage_is_positive_when_fill_price_is_worse(self) -> None:
        orders = [ManualOrder(date(2024, 1, 2), "600000.SH", Action.SELL, 100, 10.0, 1000, "exit", "")]
        fills = [Fill(date(2024, 1, 3), date(2024, 1, 2), "600000.SH", Action.SELL, 100, 9.9)]

        rows = reconcile_fills(orders, fills)

        self.assertEqual(rows[0].status, "filled")
        self.assertAlmostEqual(rows[0].slippage_bps, 100)

    def test_write_fill_reconciliation_csv(self) -> None:
        rows = reconcile_fills(
            [ManualOrder(date(2024, 1, 2), "000001.SZ", Action.BUY, 100, 10.0, 1000, "entry", "")],
            [Fill(date(2024, 1, 3), date(2024, 1, 2), "000001.SZ", Action.BUY, 100, 10.2)],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fill_reconciliation.csv"
            write_fill_reconciliation(path, rows)

            with path.open("r", encoding="utf-8", newline="") as fh:
                written = list(csv.DictReader(fh))

        self.assertEqual(written[0]["status"], "filled")
        self.assertEqual(written[0]["avg_fill_price"], "10.2000")
        self.assertEqual(written[0]["slippage_bps"], "200.00")


if __name__ == "__main__":
    unittest.main()
