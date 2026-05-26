from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional


class TushareDailySource:
    """Optional Tushare Pro downloader.

    The core project deliberately works without Tushare installed. Install the
    optional dependency and pass a token when you are ready to build the live
    data refresh job.
    """

    def __init__(self, token: str, cache_dir: Path) -> None:
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:
            raise RuntimeError("install optional dependency with: pip install '.[tushare]'") from exc

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pro = ts.pro_api(token)

    def download_daily_csv(
        self,
        symbols: Iterable[str],
        start_date: date,
        end_date: date,
    ) -> List[Path]:
        written: List[Path] = []
        start = start_date.strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")
        for symbol in symbols:
            df = self.pro.daily(ts_code=symbol, start_date=start, end_date=end)
            if df is None or df.empty:
                continue
            df = df.sort_values("trade_date")
            path = self.cache_dir / f"{symbol}.csv"
            df.to_csv(path, index=False)
            written.append(path)
        return written
