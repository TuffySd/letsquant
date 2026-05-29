import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from letsquant.data.universe import UniverseFilters, build_universe_csv, parse_exchange_set


class UniverseTests(unittest.TestCase):
    def test_build_universe_filters_st_bj_and_recent_listings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_basic = root / "stock_basic.csv"
            stock_basic.write_text(
                "ts_code,symbol,name,area,industry,list_date\n"
                "000001.SZ,000001,平安银行,深圳,银行,19910403\n"
                "000004.SZ,000004,*ST国华,深圳,软件服务,19901201\n"
                "430001.BJ,430001,北交样本,北京,机械,20100101\n"
                "688001.SH,688001,新股样本,上海,半导体,20240101\n",
                encoding="utf-8",
            )

            result = build_universe_csv(
                stock_basic_path=stock_basic,
                output_path=root / "universe.csv",
                filters=UniverseFilters(as_of_date=date(2024, 3, 1), min_listed_days=180),
            )

            self.assertEqual(result.symbols, ["000001.SZ"])
            self.assertEqual(result.excluded_count, 3)
            rows = self._read_rows(result.path)
            self.assertEqual(rows[0]["name"], "平安银行")

    def test_build_universe_filters_industries_and_exchanges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_basic = root / "stock_basic.csv"
            stock_basic.write_text(
                "ts_code,symbol,name,area,industry,list_date\n"
                "000001.SZ,000001,平安银行,深圳,银行,19910403\n"
                "600000.SH,600000,浦发银行,上海,银行,19991110\n"
                "600519.SH,600519,贵州茅台,贵州,白酒,20010827\n",
                encoding="utf-8",
            )

            result = build_universe_csv(
                stock_basic_path=stock_basic,
                output_path=root / "universe.csv",
                filters=UniverseFilters(
                    as_of_date=date(2024, 3, 1),
                    exchanges={"SH"},
                    include_industries={"银行"},
                ),
            )

            self.assertEqual(result.symbols, ["600000.SH"])

    def test_build_universe_filters_by_average_amount(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_basic = root / "stock_basic.csv"
            stock_basic.write_text(
                "ts_code,symbol,name,area,industry,list_date\n"
                "000001.SZ,000001,平安银行,深圳,银行,19910403\n"
                "000002.SZ,000002,万科A,深圳,地产,19910129\n",
                encoding="utf-8",
            )
            self._write_daily(root / "daily" / "000001.SZ.csv", [10000000, 12000000, 14000000])
            self._write_daily(root / "daily" / "000002.SZ.csv", [100000, 120000, 140000])

            result = build_universe_csv(
                stock_basic_path=stock_basic,
                output_path=root / "universe.csv",
                filters=UniverseFilters(
                    as_of_date=date(2024, 1, 5),
                    daily_dir=root / "daily",
                    liquidity_window=2,
                    min_avg_amount=1000000,
                ),
            )

            self.assertEqual(result.symbols, ["000001.SZ"])
            self.assertEqual(result.excluded_count, 1)

    def test_build_universe_sorts_by_average_amount_before_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_basic = root / "stock_basic.csv"
            stock_basic.write_text(
                "ts_code,symbol,name,area,industry,list_date\n"
                "000001.SZ,000001,平安银行,深圳,银行,19910403\n"
                "000002.SZ,000002,万科A,深圳,地产,19910129\n"
                "600000.SH,600000,浦发银行,上海,银行,19991110\n",
                encoding="utf-8",
            )
            self._write_daily(root / "daily" / "000001.SZ.csv", [10000000, 12000000, 14000000])
            self._write_daily(root / "daily" / "000002.SZ.csv", [30000000, 32000000, 34000000])
            self._write_daily(root / "daily" / "600000.SH.csv", [20000000, 22000000, 24000000])

            result = build_universe_csv(
                stock_basic_path=stock_basic,
                output_path=root / "universe.csv",
                filters=UniverseFilters(
                    as_of_date=date(2024, 1, 5),
                    daily_dir=root / "daily",
                    liquidity_window=2,
                    sort_by="avg_amount",
                    limit=2,
                ),
            )

            self.assertEqual(result.symbols, ["000002.SZ", "600000.SH"])
            rows = self._read_rows(result.path)
            self.assertEqual(rows[0]["avg_amount"], "33000000.00")

    def test_build_universe_limits_selected_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_basic = root / "stock_basic.csv"
            stock_basic.write_text(
                "ts_code,symbol,name,area,industry,list_date\n"
                "000001.SZ,000001,平安银行,深圳,银行,19910403\n"
                "000002.SZ,000002,万科A,深圳,地产,19910129\n",
                encoding="utf-8",
            )

            result = build_universe_csv(
                stock_basic_path=stock_basic,
                output_path=root / "universe.csv",
                filters=UniverseFilters(as_of_date=date(2024, 3, 1), limit=1),
            )

            self.assertEqual(result.symbols, ["000001.SZ"])

    def test_parse_exchange_set_normalizes_case(self) -> None:
        self.assertEqual(parse_exchange_set("sh, sz"), {"SH", "SZ"})

    @staticmethod
    def _write_daily(path: Path, amounts: list[int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = ["trade_date,ts_code,open,high,low,close,vol,amount"]
        for index, amount in enumerate(amounts, start=2):
            rows.append(f"2024010{index},{path.stem},10,11,9,10,1000,{amount}")
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))


if __name__ == "__main__":
    unittest.main()
