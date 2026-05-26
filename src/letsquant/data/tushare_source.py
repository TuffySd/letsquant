from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List, Optional


@dataclass(frozen=True)
class DailyDownloadResult:
    written: List[Path]
    empty_symbols: List[str]


class TushareDailySource:
    """Optional Tushare Pro downloader.

    The core project deliberately works without Tushare installed. Install the
    optional dependency and pass a token when you are ready to build the live
    data refresh job.
    """

    def __init__(
        self,
        token: str,
        cache_dir: Path,
        pro_client: Optional[Any] = None,
    ) -> None:
        if not token and pro_client is None:
            raise ValueError("Tushare token is required")

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pro = pro_client or self._build_client(token)

    def download_daily_csv(
        self,
        symbols: Iterable[str],
        start_date: date,
        end_date: date,
    ) -> List[Path]:
        return self.sync_daily_csv(symbols, start_date, end_date).written

    def sync_daily_csv(
        self,
        symbols: Iterable[str],
        start_date: date,
        end_date: date,
    ) -> DailyDownloadResult:
        written: List[Path] = []
        empty_symbols: List[str] = []
        start = start_date.strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        for symbol in symbols:
            df = self.pro.daily(ts_code=symbol, start_date=start, end_date=end)
            if df is None or df.empty:
                empty_symbols.append(symbol)
                continue
            df = df.sort_values("trade_date")
            path = self.cache_dir / f"{symbol}.csv"
            df.to_csv(path, index=False)
            written.append(path)
        return DailyDownloadResult(written=written, empty_symbols=empty_symbols)

    @staticmethod
    def _build_client(token: str) -> Any:
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:
            raise RuntimeError("install optional dependency with: pip install '.[tushare]'") from exc
        return ts.pro_api(token)
