import tempfile
import unittest
from datetime import date
from pathlib import Path

from letsquant.benchmark import build_benchmark_metrics
from letsquant.cli import apply_data_overrides
from letsquant.config import AppConfig, BenchmarkConfig, CostConfig, DataConfig, RiskConfig, StrategyConfig, load_config
from letsquant.models import Bar, PortfolioSnapshot


class BenchmarkTests(unittest.TestCase):
    def test_build_benchmark_metrics_for_backtest_window(self) -> None:
        bars = [
            Bar("000300.SH", date(2024, 1, 1), 100, 101, 99, 100),
            Bar("000300.SH", date(2024, 1, 2), 100, 112, 99, 110),
            Bar("000300.SH", date(2024, 1, 3), 110, 112, 104, 105),
            Bar("000300.SH", date(2024, 1, 4), 105, 121, 104, 120),
        ]
        snapshots = [
            PortfolioSnapshot(date(2024, 1, 2), cash=100000, market_value=0, equity=100000, positions=0, drawdown=0),
            PortfolioSnapshot(date(2024, 1, 4), cash=110000, market_value=0, equity=110000, positions=0, drawdown=0),
        ]

        metrics = build_benchmark_metrics(
            bars,
            snapshots,
            {"total_return": 0.20, "annualized_return": 0.30},
        )

        self.assertEqual(metrics["benchmark_start_close"], 110)
        self.assertEqual(metrics["benchmark_final_close"], 120)
        self.assertAlmostEqual(metrics["benchmark_total_return"], 120 / 110 - 1)
        self.assertAlmostEqual(metrics["excess_total_return"], 0.20 - (120 / 110 - 1))
        self.assertEqual(metrics["benchmark_bar_count"], 3.0)
        self.assertLess(metrics["benchmark_max_drawdown"], 0)

    def test_benchmark_requires_two_bars(self) -> None:
        bars = [Bar("000300.SH", date(2024, 1, 2), 100, 101, 99, 100)]
        snapshots = [
            PortfolioSnapshot(date(2024, 1, 2), cash=100000, market_value=0, equity=100000, positions=0, drawdown=0)
        ]

        with self.assertRaises(ValueError):
            build_benchmark_metrics(bars, snapshots, {"total_return": 0})

    def test_load_config_reads_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                """{
  "initial_cash": 100000,
  "data": {"source": "csv", "data_dir": "data/sample", "symbols": ["000001.SZ"]},
  "strategy": {"name": "trend_breakout"},
  "benchmark": {"symbol": "000300.SH", "data_dir": "data/index_daily"}
}""",
                encoding="utf-8",
            )

            config = load_config(str(path))

            self.assertIsNotNone(config.benchmark)
            self.assertEqual(config.benchmark.symbol, "000300.SH")
            self.assertEqual(config.benchmark.data_dir, Path("data/index_daily"))

    def test_cli_benchmark_overrides(self) -> None:
        config = AppConfig(
            initial_cash=100000,
            data=DataConfig(source="csv", data_dir=Path("data/sample"), symbols=["000001.SZ"]),
            strategy=StrategyConfig(name="trend_breakout"),
            risk=RiskConfig(),
            costs=CostConfig(),
            output_dir=Path("results"),
            benchmark=BenchmarkConfig(symbol="000300.SH", data_dir=Path("data/index_daily")),
        )
        args = type(
            "Args",
            (),
            {
                "symbols": None,
                "symbols_file": None,
                "data_dir": None,
                "start_date": None,
                "end_date": None,
                "output_dir": None,
                "limit": None,
                "benchmark_symbol": "000905.SH",
                "benchmark_dir": "data/index_daily_alt",
            },
        )()

        updated = apply_data_overrides(config, args)

        self.assertIsNotNone(updated.benchmark)
        self.assertEqual(updated.benchmark.symbol, "000905.SH")
        self.assertEqual(updated.benchmark.data_dir, Path("data/index_daily_alt"))


if __name__ == "__main__":
    unittest.main()
