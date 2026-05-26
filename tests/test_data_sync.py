import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Dict, List

from letsquant.cli import _resolve_symbols, _split_symbols
from letsquant.data.tushare_source import TushareDailySource


class FakeFrame:
    def __init__(self, rows: List[Dict[str, object]]) -> None:
        self.rows = rows
        self.empty = not rows

    def sort_values(self, column: str) -> "FakeFrame":
        return FakeFrame(sorted(self.rows, key=lambda row: row[column]))

    def to_csv(self, path: Path, index: bool = False) -> None:
        fieldnames = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)


class FakeTushareClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, str]] = []

    def daily(self, ts_code: str, start_date: str, end_date: str) -> FakeFrame:
        self.calls.append(
            {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        if ts_code == "EMPTY.SZ":
            return FakeFrame([])
        return FakeFrame(
            [
                {
                    "ts_code": ts_code,
                    "trade_date": "20240103",
                    "open": 10.2,
                    "high": 10.4,
                    "low": 10.1,
                    "close": 10.3,
                    "vol": 1200,
                    "amount": 12345,
                },
                {
                    "ts_code": ts_code,
                    "trade_date": "20240102",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.8,
                    "close": 10.1,
                    "vol": 1000,
                    "amount": 10000,
                },
            ]
        )


class DataSyncTests(unittest.TestCase):
    def test_tushare_source_writes_sorted_daily_csv(self) -> None:
        client = FakeTushareClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = TushareDailySource(
                token="test-token",
                cache_dir=Path(temp_dir),
                pro_client=client,
            )
            result = source.sync_daily_csv(
                ["000001.SZ", "EMPTY.SZ"],
                date(2024, 1, 1),
                date(2024, 1, 31),
            )

            self.assertEqual(len(result.written), 1)
            self.assertEqual(result.empty_symbols, ["EMPTY.SZ"])
            self.assertEqual(client.calls[0]["start_date"], "20240101")
            self.assertEqual(client.calls[0]["end_date"], "20240131")

            with result.written[0].open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual([row["trade_date"] for row in rows], ["20240102", "20240103"])
            self.assertEqual(rows[0]["ts_code"], "000001.SZ")

    def test_symbol_parsing_dedupes_inputs(self) -> None:
        self.assertEqual(_split_symbols("000001.SZ, 000002.SZ\n# comment"), ["000001.SZ", "000002.SZ"])
        symbols = _resolve_symbols("000001.SZ,000001.SZ", None, None)
        self.assertEqual(symbols, ["000001.SZ"])


if __name__ == "__main__":
    unittest.main()
