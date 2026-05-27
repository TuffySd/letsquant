import csv
from dataclasses import dataclass, field
from datetime import date
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class DailyDownloadResult:
    written: List[Path]
    empty_symbols: List[str]


@dataclass(frozen=True)
class MarketDataSyncResult:
    daily: DailyDownloadResult
    adj_factor: List[Path]
    limit: List[Path]
    suspension: List[Path]
    stock_basic: Optional[Path] = None
    index_daily: List[Path] = field(default_factory=list)


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
            rows = self._frame_rows(df)
            if not rows:
                empty_symbols.append(symbol)
                continue
            rows = sorted(rows, key=lambda row: str(row["trade_date"]))
            path = self.cache_dir / f"{symbol}.csv"
            self._write_rows(path, rows)
            written.append(path)
        return DailyDownloadResult(written=written, empty_symbols=empty_symbols)

    def sync_market_data_csv(
        self,
        symbols: Iterable[str],
        start_date: date,
        end_date: date,
        include_adj_factor: bool = False,
        include_constraints: bool = False,
        include_stock_basic: bool = False,
        index_symbols: Optional[Iterable[str]] = None,
    ) -> MarketDataSyncResult:
        symbol_list = list(symbols)
        start = start_date.strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")

        constraints = ConstraintCache.empty()
        if include_constraints:
            trade_dates = self._collect_daily_trade_dates(symbol_list, start, end)
            constraints = self._sync_constraints_csv(trade_dates, set(symbol_list))

        daily = self._sync_daily_rows(symbol_list, start, end, constraints)
        adj_factor = self._sync_adj_factor_csv(symbol_list, start, end) if include_adj_factor else []
        stock_basic = self._sync_stock_basic_csv() if include_stock_basic else None
        index_daily = self._sync_index_daily_csv(index_symbols or [], start, end)
        return MarketDataSyncResult(
            daily=daily,
            adj_factor=adj_factor,
            limit=constraints.limit_paths,
            suspension=constraints.suspension_paths,
            stock_basic=stock_basic,
            index_daily=index_daily,
        )

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
        try:
            return getattr(self.pro, method)(**params)
        except Exception as exc:
            raise RuntimeError(f"Tushare {method} request failed: {exc}") from exc

    def _sync_daily_rows(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        constraints: "ConstraintCache",
    ) -> DailyDownloadResult:
        written: List[Path] = []
        empty_symbols: List[str] = []
        for symbol in symbols:
            rows = self._frame_rows(self._call_pro("daily", ts_code=symbol, start_date=start, end_date=end))
            if not rows:
                empty_symbols.append(symbol)
                continue
            rows = sorted(rows, key=lambda row: str(row["trade_date"]))
            if constraints.has_data:
                rows = [constraints.enrich_daily_row(row) for row in rows]
            path = self.cache_dir / f"{symbol}.csv"
            self._write_rows(path, rows)
            written.append(path)
        return DailyDownloadResult(written=written, empty_symbols=empty_symbols)

    def _collect_daily_trade_dates(self, symbols: Iterable[str], start: str, end: str) -> List[str]:
        dates: Set[str] = set()
        for symbol in symbols:
            rows = self._frame_rows(self._call_pro("daily", ts_code=symbol, start_date=start, end_date=end))
            for row in rows:
                value = row.get("trade_date")
                if value:
                    dates.add(str(value))
        return sorted(dates)

    def _sync_adj_factor_csv(self, symbols: Iterable[str], start: str, end: str) -> List[Path]:
        out_dir = self.cache_dir.parent / "adj_factor"
        written: List[Path] = []
        for symbol in symbols:
            rows = self._frame_rows(self._call_pro("adj_factor", ts_code=symbol, start_date=start, end_date=end))
            if not rows:
                continue
            rows = sorted(rows, key=lambda row: str(row["trade_date"]))
            path = out_dir / f"{symbol}.csv"
            self._write_rows(path, rows)
            written.append(path)
        return written

    def _sync_constraints_csv(self, trade_dates: Iterable[str], symbols: Set[str]) -> "ConstraintCache":
        limit_rows: List[Dict[str, Any]] = []
        suspension_rows: List[Dict[str, Any]] = []
        limit_paths: List[Path] = []
        suspension_paths: List[Path] = []

        limit_dir = self.cache_dir.parent / "limits"
        suspension_dir = self.cache_dir.parent / "suspensions"
        for trade_date in trade_dates:
            day_limit_rows = self._filter_symbol_rows(
                self._frame_rows(self._call_pro("stk_limit", trade_date=trade_date)),
                symbols,
            )
            if day_limit_rows:
                path = limit_dir / f"{trade_date}.csv"
                self._write_rows(path, sorted(day_limit_rows, key=lambda row: str(row.get("ts_code", ""))))
                limit_paths.append(path)
                limit_rows.extend(day_limit_rows)

            day_suspension_rows = self._filter_symbol_rows(
                self._frame_rows(self._call_pro("suspend_d", trade_date=trade_date)),
                symbols,
            )
            if day_suspension_rows:
                path = suspension_dir / f"{trade_date}.csv"
                self._write_rows(path, sorted(day_suspension_rows, key=lambda row: str(row.get("ts_code", ""))))
                suspension_paths.append(path)
                suspension_rows.extend(day_suspension_rows)

        return ConstraintCache.from_rows(limit_rows, suspension_rows, limit_paths, suspension_paths)

    def _sync_stock_basic_csv(self) -> Optional[Path]:
        rows = self._frame_rows(
            self._call_pro(
                "stock_basic",
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,list_date",
            )
        )
        if not rows:
            return None
        path = self.cache_dir.parent / "stocks" / "stock_basic.csv"
        self._write_rows(path, sorted(rows, key=lambda row: str(row.get("ts_code", ""))))
        return path

    def _sync_index_daily_csv(self, index_symbols: Iterable[str], start: str, end: str) -> List[Path]:
        out_dir = self.cache_dir.parent / "index_daily"
        written: List[Path] = []
        for symbol in index_symbols:
            rows = self._frame_rows(self._call_pro("index_daily", ts_code=symbol, start_date=start, end_date=end))
            if not rows:
                continue
            rows = sorted(rows, key=lambda row: str(row["trade_date"]))
            path = out_dir / f"{symbol}.csv"
            self._write_rows(path, rows)
            written.append(path)
        return written

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

    @staticmethod
    def _frame_rows(df: Any) -> List[Dict[str, Any]]:
        if df is None:
            return []
        if hasattr(df, "empty") and df.empty:
            return []
        if hasattr(df, "to_dict"):
            return [dict(row) for row in df.to_dict("records")]
        if hasattr(df, "rows"):
            return [dict(row) for row in df.rows]
        raise TypeError(f"unsupported dataframe type: {type(df).__name__}")

    @staticmethod
    def _filter_symbol_rows(rows: Iterable[Dict[str, Any]], symbols: Set[str]) -> List[Dict[str, Any]]:
        return [row for row in rows if str(row.get("ts_code", "")) in symbols]

    @staticmethod
    def _write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: List[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


@dataclass(frozen=True)
class ConstraintCache:
    limits: Dict[Tuple[str, str], Dict[str, Any]]
    suspensions: Set[Tuple[str, str]]
    limit_paths: List[Path]
    suspension_paths: List[Path]

    @property
    def has_data(self) -> bool:
        return bool(self.limits or self.suspensions)

    def enrich_daily_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(row)
        key = (str(row.get("ts_code", "")), str(row.get("trade_date", "")))
        limit = self.limits.get(key, {})
        enriched["limit_up"] = limit.get("up_limit", limit.get("limit_up", ""))
        enriched["limit_down"] = limit.get("down_limit", limit.get("limit_down", ""))
        enriched["is_suspended"] = 1 if key in self.suspensions else 0
        return enriched

    @classmethod
    def empty(cls) -> "ConstraintCache":
        return cls(limits={}, suspensions=set(), limit_paths=[], suspension_paths=[])

    @classmethod
    def from_rows(
        cls,
        limit_rows: Iterable[Dict[str, Any]],
        suspension_rows: Iterable[Dict[str, Any]],
        limit_paths: List[Path],
        suspension_paths: List[Path],
    ) -> "ConstraintCache":
        limits: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in limit_rows:
            trade_date = row.get("trade_date")
            symbol = row.get("ts_code")
            if trade_date and symbol:
                limits[(str(symbol), str(trade_date))] = dict(row)

        suspensions: Set[Tuple[str, str]] = set()
        for row in suspension_rows:
            symbol = row.get("ts_code")
            trade_date = row.get("trade_date") or row.get("suspend_date")
            if symbol and trade_date:
                suspensions.add((str(symbol), str(trade_date)))

        return cls(
            limits=limits,
            suspensions=suspensions,
            limit_paths=limit_paths,
            suspension_paths=suspension_paths,
        )


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
