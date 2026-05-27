import csv
import tempfile
import unittest
from pathlib import Path

from letsquant.data.adjusted_price import build_adjusted_daily_csv


class AdjustedPriceTests(unittest.TestCase):
    def test_builds_qfq_daily_from_cached_factors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_daily(root / "daily" / "000001.SZ.csv")
            self._write_factors(root / "adj_factor" / "000001.SZ.csv")

            result = build_adjusted_daily_csv(
                symbols=["000001.SZ"],
                daily_dir=root / "daily",
                adj_factor_dir=root / "adj_factor",
                output_dir=root / "qfq_daily",
                mode="qfq",
            )

            self.assertEqual(result.skipped_symbols, [])
            rows = self._read_rows(result.written[0])
            self.assertEqual(rows[0]["open"], "5")
            self.assertEqual(rows[1]["open"], "11")
            self.assertEqual(rows[0]["limit_up"], "6.05")
            self.assertEqual(rows[1]["limit_up"], "13.2")
            self.assertEqual(rows[0]["adj_factor"], "1")
            self.assertEqual(rows[0]["adjustment"], "qfq")

    def test_builds_hfq_daily_from_cached_factors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_daily(root / "daily" / "000001.SZ.csv")
            self._write_factors(root / "adj_factor" / "000001.SZ.csv")

            result = build_adjusted_daily_csv(
                symbols=["000001.SZ"],
                daily_dir=root / "daily",
                adj_factor_dir=root / "adj_factor",
                output_dir=root / "hfq_daily",
                mode="hfq",
            )

            rows = self._read_rows(result.written[0])
            self.assertEqual(rows[0]["open"], "10")
            self.assertEqual(rows[1]["open"], "22")
            self.assertEqual(rows[0]["limit_up"], "12.1")
            self.assertEqual(rows[1]["limit_up"], "26.4")
            self.assertEqual(rows[1]["adjustment"], "hfq")

    def test_skips_symbols_without_factor_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_daily(root / "daily" / "000001.SZ.csv")

            result = build_adjusted_daily_csv(
                symbols=["000001.SZ"],
                daily_dir=root / "daily",
                adj_factor_dir=root / "adj_factor",
                output_dir=root / "qfq_daily",
            )

            self.assertEqual(result.written, [])
            self.assertEqual(result.skipped_symbols, ["000001.SZ"])

    @staticmethod
    def _write_daily(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "trade_date,ts_code,open,high,low,close,pre_close,vol,amount,limit_up,limit_down,is_suspended\n"
            "20240102,000001.SZ,10,12,9,11,9,1000,10000,12.1,9.9,0\n"
            "20240103,000001.SZ,11,13,10,12,11,1100,12000,13.2,10.8,0\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_factors(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "trade_date,ts_code,adj_factor\n"
            "20240102,000001.SZ,1\n"
            "20240103,000001.SZ,2\n",
            encoding="utf-8",
        )

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))


if __name__ == "__main__":
    unittest.main()
