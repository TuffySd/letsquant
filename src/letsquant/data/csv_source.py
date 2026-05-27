import csv
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from letsquant.config import parse_date
from letsquant.models import Bar


class CsvBarSource:
    """Loads daily bars from one CSV file per symbol."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def load_bars(
        self,
        symbols: Iterable[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, List[Bar]]:
        result: Dict[str, List[Bar]] = {}
        for symbol in symbols:
            bars = self._load_symbol(symbol, start_date, end_date)
            if bars:
                result[symbol] = bars
        return result

    def _load_symbol(
        self,
        symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Bar]:
        path = self.data_dir / f"{symbol}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing CSV data for {symbol}: {path}")

        bars: List[Bar] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                bar_date = self._row_date(row)
                if start_date and bar_date < start_date:
                    continue
                if end_date and bar_date > end_date:
                    continue
                bars.append(
                    Bar(
                        symbol=row.get("ts_code") or row.get("symbol") or symbol,
                        date=bar_date,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("vol") or row.get("volume") or 0),
                        amount=self._optional_float(row.get("amount")),
                        is_suspended=self._optional_bool(
                            row.get("is_suspended") or row.get("suspended") or row.get("paused")
                        ),
                        limit_up=self._optional_float(row.get("limit_up") or row.get("up_limit")),
                        limit_down=self._optional_float(row.get("limit_down") or row.get("down_limit")),
                    )
                )

        bars.sort(key=lambda item: item.date)
        self._ensure_unique_dates(symbol, bars)
        return bars

    @staticmethod
    def _row_date(row: Dict[str, str]) -> date:
        value = row.get("trade_date") or row.get("date")
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(f"missing trade_date/date in row: {row}")
        return parsed

    @staticmethod
    def _optional_float(value: Optional[str]) -> Optional[float]:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _optional_bool(value: Optional[str]) -> bool:
        if value is None:
            return False
        text = str(value).strip().lower()
        if text in ("", "0", "false", "f", "no", "n"):
            return False
        if text in ("1", "true", "t", "yes", "y"):
            return True
        raise ValueError(f"invalid boolean value: {value}")

    @staticmethod
    def _ensure_unique_dates(symbol: str, bars: List[Bar]) -> None:
        seen = set()
        for bar in bars:
            if bar.date in seen:
                raise ValueError(f"duplicate bar date for {symbol}: {bar.date}")
            seen.add(bar.date)
