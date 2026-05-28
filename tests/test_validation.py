import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date
from io import StringIO
from pathlib import Path

from letsquant.cli import run_validation, validate_split_date
from letsquant.config import AppConfig, CostConfig, DataConfig, RiskConfig, StrategyConfig


class ValidationTests(unittest.TestCase):
    def test_run_validation_writes_in_and_out_sample_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "validation"
            config = AppConfig(
                initial_cash=100000,
                data=DataConfig(
                    source="csv",
                    data_dir=Path("data/sample"),
                    symbols=["000001.SZ"],
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 30),
                ),
                strategy=StrategyConfig(
                    name="trend_breakout",
                    params={
                        "short_window": 5,
                        "mid_window": 10,
                        "long_window": 20,
                        "breakout_window": 10,
                        "momentum_window": 10,
                        "min_momentum": 0.02,
                        "volume_window": 10,
                        "min_volume_ratio": 0.8,
                        "stop_loss_pct": 0.08,
                        "trailing_stop_pct": 0.12,
                        "max_holding_days": 45,
                    },
                ),
                risk=RiskConfig(max_position_pct=0.2, max_positions=5, cash_reserve_pct=0.05),
                costs=CostConfig(slippage_bps=0),
                output_dir=output_dir,
            )

            with redirect_stdout(StringIO()):
                run_validation(config, date(2024, 2, 15))

            report_path = output_dir / "validation_metrics.json"
            self.assertTrue(report_path.exists())
            self.assertTrue((output_dir / "in_sample" / "metrics.json").exists())
            self.assertTrue((output_dir / "out_sample" / "metrics.json").exists())
            with report_path.open("r", encoding="utf-8") as fh:
                report = json.load(fh)
            self.assertEqual(report["split_date"], "2024-02-15")
            self.assertIn("total_return", report["in_sample"]["metrics"])
            self.assertIn("total_return", report["out_sample"]["metrics"])
            self.assertIn("out_sample_trade_count", report["robustness"])

    def test_validate_split_date_rejects_empty_periods(self) -> None:
        config = AppConfig(
            initial_cash=100000,
            data=DataConfig(
                source="csv",
                data_dir=Path("data/sample"),
                symbols=["000001.SZ"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 4, 30),
            ),
            strategy=StrategyConfig(name="trend_breakout"),
            risk=RiskConfig(),
            costs=CostConfig(),
            output_dir=Path("results"),
        )

        with self.assertRaises(ValueError):
            validate_split_date(config, date(2024, 1, 1))
        with self.assertRaises(ValueError):
            validate_split_date(config, date(2024, 4, 30))

        validate_split_date(replace(config, data=replace(config.data, start_date=None, end_date=None)), date(2024, 2, 1))


if __name__ == "__main__":
    unittest.main()
