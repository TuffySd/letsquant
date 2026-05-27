from dataclasses import dataclass
from datetime import date
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class DailyDownloadResult:
    written: List[Path]
    empty_symbols: List[str]


@dataclass(frozen=True)
class TushareProbeCase:
    name: str
    method: str
    params: Dict[str, Any]
    required_for: str


@dataclass(frozen=True)
class TushareProbeResult:
    name: str
    method: str
    required_for: str
    ok: bool
    rows: int
    columns: List[str]
    error: str = ""


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
        api_url: Optional[str] = None,
        request_interval: float = 0.0,
        pro_client: Optional[Any] = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if not token and pro_client is None:
            raise ValueError("Tushare token is required")
        if request_interval < 0:
            raise ValueError("request_interval cannot be negative")

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_interval = request_interval
        self._sleeper = sleeper
        self._last_request_at: Optional[float] = None
        self.pro = pro_client or self._build_client(token, api_url)
        if api_url and pro_client is not None:
            self._set_api_url(self.pro, api_url)

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
            df = self._call_pro("daily", ts_code=symbol, start_date=start, end_date=end)
            if df is None or df.empty:
                empty_symbols.append(symbol)
                continue
            df = df.sort_values("trade_date")
            path = self.cache_dir / f"{symbol}.csv"
            df.to_csv(path, index=False)
            written.append(path)
        return DailyDownloadResult(written=written, empty_symbols=empty_symbols)

    def probe_permissions(self, cases: Iterable[TushareProbeCase]) -> List[TushareProbeResult]:
        results: List[TushareProbeResult] = []
        for case in cases:
            try:
                df = self._call_pro(case.method, **case.params)
                rows = 0 if df is None else len(df)
                columns = [] if df is None else [str(column) for column in getattr(df, "columns", [])]
                results.append(
                    TushareProbeResult(
                        name=case.name,
                        method=case.method,
                        required_for=case.required_for,
                        ok=True,
                        rows=rows,
                        columns=columns,
                    )
                )
            except Exception as exc:
                results.append(
                    TushareProbeResult(
                        name=case.name,
                        method=case.method,
                        required_for=case.required_for,
                        ok=False,
                        rows=0,
                        columns=[],
                        error=str(exc),
                    )
                )
        return results

    def _call_pro(self, method: str, **params: Any) -> Any:
        self._wait_for_rate_limit()
        return getattr(self.pro, method)(**params)

    def _wait_for_rate_limit(self) -> None:
        if self.request_interval <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            wait_seconds = self.request_interval - elapsed
            if wait_seconds > 0:
                self._sleeper(wait_seconds)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _build_client(token: str, api_url: Optional[str]) -> Any:
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:
            raise RuntimeError("install optional dependency with: pip install '.[tushare]'") from exc
        pro = ts.pro_api(token)
        if api_url:
            TushareDailySource._set_api_url(pro, api_url)
        return pro

    @staticmethod
    def _set_api_url(pro: Any, api_url: str) -> None:
        setattr(pro, "_DataApi__http_url", api_url)


def default_probe_cases(symbol: str, trade_date: date, news_source: str = "sina") -> List[TushareProbeCase]:
    trade_date_text = trade_date.strftime("%Y%m%d")
    start_date_text = trade_date_text
    end_date_text = trade_date_text
    news_day = trade_date.isoformat()
    return [
        TushareProbeCase(
            name="交易日历",
            method="trade_cal",
            params={
                "exchange": "",
                "start_date": start_date_text,
                "end_date": end_date_text,
                "fields": "exchange,cal_date,is_open,pretrade_date",
            },
            required_for="交易日对齐",
        ),
        TushareProbeCase(
            name="股票基础信息",
            method="stock_basic",
            params={
                "exchange": "",
                "list_status": "L",
                "fields": "ts_code,symbol,name,area,industry,list_date",
            },
            required_for="股票池",
        ),
        TushareProbeCase(
            name="A股日线",
            method="daily",
            params={
                "ts_code": symbol,
                "start_date": start_date_text,
                "end_date": end_date_text,
            },
            required_for="行情缓存",
        ),
        TushareProbeCase(
            name="复权因子",
            method="adj_factor",
            params={
                "ts_code": symbol,
                "start_date": start_date_text,
                "end_date": end_date_text,
            },
            required_for="复权价格",
        ),
        TushareProbeCase(
            name="每日涨跌停价格",
            method="stk_limit",
            params={
                "trade_date": trade_date_text,
            },
            required_for="涨跌停成交约束",
        ),
        TushareProbeCase(
            name="每日停复牌信息",
            method="suspend_d",
            params={
                "trade_date": trade_date_text,
            },
            required_for="停牌成交约束",
        ),
        TushareProbeCase(
            name="指数日线",
            method="index_daily",
            params={
                "ts_code": "000300.SH",
                "start_date": start_date_text,
                "end_date": end_date_text,
            },
            required_for="基准对比",
        ),
        TushareProbeCase(
            name="新闻快讯",
            method="news",
            params={
                "src": news_source,
                "start_date": f"{news_day} 09:00:00",
                "end_date": f"{news_day} 10:00:00",
            },
            required_for="宏观/热点复核",
        ),
        TushareProbeCase(
            name="上市公司公告",
            method="anns_d",
            params={
                "ann_date": trade_date_text,
            },
            required_for="公告风险复核",
        ),
    ]
