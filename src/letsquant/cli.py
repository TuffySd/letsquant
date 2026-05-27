import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from letsquant.config import AppConfig, load_config, parse_date
from letsquant.data import CsvBarSource
from letsquant.data.adjusted_price import build_adjusted_daily_csv
from letsquant.data.tushare_source import TushareDailySource, default_probe_cases
from letsquant.data.universe import (
    UniverseFilters,
    build_universe_csv,
    parse_csv_set,
    parse_exchange_set,
)
from letsquant.execution import Backtester
from letsquant.execution.instructions import build_manual_orders
from letsquant.models import Action, Bar, Position, Signal
from letsquant.reports import (
    ensure_output_dir,
    write_equity_curve,
    write_metrics,
    write_manual_orders,
    write_order_rejections,
    write_signals,
    write_trades,
)
from letsquant.strategies import build_strategy


def main() -> None:
    parser = argparse.ArgumentParser(prog="letsquant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser("backtest", help="run historical backtest")
    backtest_parser.add_argument("--config", required=True, help="path to JSON config")

    signal_parser = subparsers.add_parser("signal", help="generate latest manual trade signals")
    signal_parser.add_argument("--config", required=True, help="path to JSON config")
    signal_parser.add_argument("--portfolio", help="optional live portfolio JSON")

    data_parser = subparsers.add_parser("data", help="data maintenance commands")
    data_subparsers = data_parser.add_subparsers(dest="data_command", required=True)
    sync_parser = data_subparsers.add_parser("sync", help="sync market data into local CSV cache")
    sync_parser.add_argument("--provider", choices=["tushare"], default="tushare")
    sync_parser.add_argument("--config", help="optional app config for data_dir, symbols, and dates")
    sync_parser.add_argument("--symbols", help="comma-separated symbols, e.g. 000001.SZ,000002.SZ")
    sync_parser.add_argument("--symbols-file", help="file with symbols separated by lines or commas")
    sync_parser.add_argument("--start-date", help="inclusive start date, YYYY-MM-DD or YYYYMMDD")
    sync_parser.add_argument("--end-date", help="inclusive end date, defaults to today")
    sync_parser.add_argument("--cache-dir", help="output CSV cache directory, defaults to config data_dir")
    sync_parser.add_argument(
        "--with-adj-factor",
        action="store_true",
        help="also cache Tushare adj_factor data under data/adj_factor",
    )
    sync_parser.add_argument(
        "--with-constraints",
        action="store_true",
        help="also cache and merge stk_limit/suspend_d constraints into daily CSV",
    )
    sync_parser.add_argument(
        "--with-stock-basic",
        action="store_true",
        help="also cache listed stock metadata under data/stocks",
    )
    sync_parser.add_argument(
        "--index-symbols",
        help="comma-separated index symbols to cache under data/index_daily, e.g. 000300.SH,000905.SH",
    )
    sync_parser.add_argument(
        "--token-env",
        default="TUSHARE_TOKEN",
        help="environment variable containing the Tushare token",
    )
    sync_parser.add_argument(
        "--api-url-env",
        default="TUSHARE_API_URL",
        help="optional environment variable containing a Tushare-compatible API URL",
    )
    sync_parser.add_argument(
        "--request-interval",
        type=float,
        default=0.5,
        help="seconds between provider requests; 0.5 respects 120 requests/minute",
    )
    probe_parser = data_subparsers.add_parser("probe", help="probe Tushare token permissions")
    probe_parser.add_argument("--provider", choices=["tushare"], default="tushare")
    probe_parser.add_argument("--symbol", default="000001.SZ", help="sample A-share symbol")
    probe_parser.add_argument("--trade-date", default="2024-01-02", help="sample trade date")
    probe_parser.add_argument("--news-source", default="sina", help="sample news source, e.g. sina or cls")
    probe_parser.add_argument(
        "--token-env",
        default="TUSHARE_TOKEN",
        help="environment variable containing the Tushare token",
    )
    probe_parser.add_argument(
        "--api-url-env",
        default="TUSHARE_API_URL",
        help="optional environment variable containing a Tushare-compatible API URL",
    )
    probe_parser.add_argument(
        "--request-interval",
        type=float,
        default=0.5,
        help="seconds between provider requests; 0.5 respects 120 requests/minute",
    )
    adjust_parser = data_subparsers.add_parser("adjust", help="build adjusted daily CSV from cached data")
    adjust_parser.add_argument("--config", help="optional app config for symbols and data_dir")
    adjust_parser.add_argument("--symbols", help="comma-separated symbols, e.g. 000001.SZ,000002.SZ")
    adjust_parser.add_argument("--symbols-file", help="file with symbols separated by lines or commas")
    adjust_parser.add_argument("--daily-dir", help="raw daily CSV directory, defaults to config data_dir")
    adjust_parser.add_argument("--adj-factor-dir", default="data/adj_factor", help="adj_factor CSV directory")
    adjust_parser.add_argument(
        "--mode",
        choices=["qfq", "hfq"],
        default="qfq",
        help="qfq for forward-adjusted prices, hfq for backward-adjusted prices",
    )
    adjust_parser.add_argument("--output-dir", help="output directory, defaults to data/<mode>_daily")
    universe_parser = data_subparsers.add_parser("universe", help="build a stock universe from stock_basic CSV")
    universe_parser.add_argument("--stock-basic", default="data/stocks/stock_basic.csv", help="stock_basic CSV path")
    universe_parser.add_argument("--output", default="data/universe/default.csv", help="output universe CSV path")
    universe_parser.add_argument("--as-of-date", help="filter date, YYYY-MM-DD or YYYYMMDD; defaults to today")
    universe_parser.add_argument("--min-listed-days", type=int, default=180, help="minimum listed calendar days")
    universe_parser.add_argument("--exchanges", default="SH,SZ", help="allowed exchanges, e.g. SH,SZ,BJ")
    universe_parser.add_argument("--include-bj", action="store_true", help="include Beijing Stock Exchange listings")
    universe_parser.add_argument("--include-st", action="store_true", help="include ST and *ST names")
    universe_parser.add_argument("--include-industries", help="comma-separated industries to keep")
    universe_parser.add_argument("--exclude-industries", help="comma-separated industries to remove")
    universe_parser.add_argument("--daily-dir", default="data/daily", help="daily CSV directory for liquidity filters")
    universe_parser.add_argument("--liquidity-window", type=int, default=20, help="recent bars used for avg amount")
    universe_parser.add_argument("--min-avg-amount", type=float, help="minimum average amount over liquidity window")

    args = parser.parse_args()

    try:
        if args.command == "backtest":
            config = load_config(args.config)
            run_backtest(config)
        elif args.command == "signal":
            config = load_config(args.config)
            run_signal(config, args.portfolio)
        elif args.command == "data" and args.data_command == "sync":
            run_data_sync(args)
        elif args.command == "data" and args.data_command == "probe":
            run_data_probe(args)
        elif args.command == "data" and args.data_command == "adjust":
            run_data_adjust(args)
        elif args.command == "data" and args.data_command == "universe":
            run_data_universe(args)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def run_backtest(config: AppConfig) -> None:
    bars_by_symbol = load_bars(config)
    strategy = build_strategy(config.strategy.name, config.strategy.params)
    backtester = Backtester(strategy, config.initial_cash, config.risk, config.costs)
    result = backtester.run(bars_by_symbol)

    output_dir = ensure_output_dir(config.output_dir)
    write_metrics(output_dir / "metrics.json", result.metrics)
    write_trades(output_dir / "trades.csv", result.trades)
    write_order_rejections(output_dir / "order_rejections.csv", result.order_rejections)
    write_signals(output_dir / "signals.csv", result.signals)
    write_equity_curve(output_dir / "equity_curve.csv", result.snapshots)

    print(f"Backtest complete. Output: {output_dir}")
    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))


def run_signal(config: AppConfig, portfolio_path: Optional[str]) -> None:
    bars_by_symbol = load_bars(config)
    strategy = build_strategy(config.strategy.name, config.strategy.params)
    cash, positions = load_portfolio(portfolio_path, config.initial_cash)
    signals: List[Signal] = []

    for symbol, bars in sorted(bars_by_symbol.items()):
        if not bars:
            continue
        signal = strategy.generate(symbol, bars, positions.get(symbol))
        if signal.action != Action.HOLD:
            signals.append(signal)

    output_dir = ensure_output_dir(config.output_dir)
    write_signals(output_dir / "current_signals.csv", signals)
    orders = build_manual_orders(
        signals,
        bars_by_symbol,
        cash=cash,
        positions=positions,
        risk=config.risk,
        costs=config.costs,
    )
    write_manual_orders(output_dir / "manual_orders.csv", orders)
    print(f"Signal generation complete. Output: {output_dir / 'current_signals.csv'}")
    for order in orders:
        print(
            f"{order.signal_date} {order.symbol} {order.action.value} "
            f"shares={order.shares} ref={order.reference_price:.2f} reason={order.reason}"
        )
    if not orders:
        print("No actionable signals.")


def load_bars(config: AppConfig) -> Dict[str, List[Bar]]:
    if config.data.source != "csv":
        raise ValueError(f"unsupported data source in CLI: {config.data.source}")
    if not config.data.symbols:
        raise ValueError("config.data.symbols cannot be empty")
    source = CsvBarSource(config.data.data_dir)
    bars_by_symbol = source.load_bars(
        config.data.symbols,
        start_date=config.data.start_date,
        end_date=config.data.end_date,
    )
    if not bars_by_symbol:
        raise ValueError("no market data loaded")
    return bars_by_symbol


def run_data_sync(args: argparse.Namespace) -> None:
    config = load_config(args.config) if args.config else None
    if args.provider != "tushare":
        raise ValueError(f"unsupported data provider: {args.provider}")

    symbols = _resolve_symbols(args.symbols, args.symbols_file, config)
    start_date = _resolve_start_date(args.start_date, config)
    end_date = parse_date(args.end_date) if args.end_date else None
    if end_date is None:
        end_date = date.today()
    if start_date > end_date:
        raise ValueError("start-date cannot be later than end-date")

    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    if cache_dir is None and config is not None:
        cache_dir = config.data.data_dir
    if cache_dir is None:
        cache_dir = Path("data/daily")

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise ValueError(f"missing Tushare token; set environment variable {args.token_env}")

    api_url = _optional_env(args.api_url_env)
    source = TushareDailySource(
        token=token,
        cache_dir=cache_dir,
        api_url=api_url,
        request_interval=args.request_interval,
    )
    index_symbols = _split_symbols(args.index_symbols) if args.index_symbols else []
    result = source.sync_market_data_csv(
        symbols,
        start_date,
        end_date,
        include_adj_factor=args.with_adj_factor,
        include_constraints=args.with_constraints,
        include_stock_basic=args.with_stock_basic,
        index_symbols=index_symbols,
    )
    print(
        "Data sync complete. "
        f"provider={args.provider} cache_dir={cache_dir} "
        f"api_url={'custom' if api_url else 'default'} "
        f"request_interval={args.request_interval:.2f}s "
        f"requested={len(symbols)} written={len(result.daily.written)} empty={len(result.daily.empty_symbols)} "
        f"adj_factor={len(result.adj_factor)} limits={len(result.limit)} "
        f"suspensions={len(result.suspension)} index_daily={len(result.index_daily)} "
        f"stock_basic={1 if result.stock_basic else 0}"
    )
    for path in result.daily.written:
        print(path)
    for path in result.adj_factor:
        print(path)
    for path in result.limit:
        print(path)
    for path in result.suspension:
        print(path)
    if result.stock_basic:
        print(result.stock_basic)
    for path in result.index_daily:
        print(path)
    if result.daily.empty_symbols:
        print("Empty symbols: " + ",".join(result.daily.empty_symbols))


def run_data_probe(args: argparse.Namespace) -> None:
    if args.provider != "tushare":
        raise ValueError(f"unsupported data provider: {args.provider}")
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise ValueError(f"missing Tushare token; set environment variable {args.token_env}")

    trade_date = parse_date(args.trade_date)
    if trade_date is None:
        raise ValueError("trade-date is required")
    api_url = _optional_env(args.api_url_env)
    source = TushareDailySource(
        token=token,
        cache_dir=Path("data/daily"),
        api_url=api_url,
        request_interval=args.request_interval,
    )
    cases = default_probe_cases(args.symbol, trade_date, args.news_source)
    results = source.probe_permissions(cases)

    print(
        "Tushare probe complete. "
        f"api_url={'custom' if api_url else 'default'} "
        f"request_interval={args.request_interval:.2f}s "
        f"cases={len(results)} ok={sum(1 for item in results if item.ok)} "
        f"failed={sum(1 for item in results if not item.ok)}"
    )
    for item in results:
        status = "OK" if item.ok else "FAIL"
        columns = ",".join(item.columns[:6])
        detail = f"rows={item.rows} columns={columns}" if item.ok else _compact_error(item.error)
        print(f"{status} {item.method} {item.name} [{item.required_for}] {detail}")


def run_data_adjust(args: argparse.Namespace) -> None:
    config = load_config(args.config) if args.config else None
    symbols = _resolve_symbols(args.symbols, args.symbols_file, config)
    daily_dir = Path(args.daily_dir) if args.daily_dir else None
    if daily_dir is None and config is not None:
        daily_dir = config.data.data_dir
    if daily_dir is None:
        daily_dir = Path("data/daily")
    output_dir = Path(args.output_dir) if args.output_dir else Path(f"data/{args.mode}_daily")

    result = build_adjusted_daily_csv(
        symbols=symbols,
        daily_dir=daily_dir,
        adj_factor_dir=Path(args.adj_factor_dir),
        output_dir=output_dir,
        mode=args.mode,
    )
    print(
        "Adjusted daily build complete. "
        f"mode={args.mode} daily_dir={daily_dir} adj_factor_dir={args.adj_factor_dir} "
        f"output_dir={output_dir} requested={len(symbols)} "
        f"written={len(result.written)} skipped={len(result.skipped_symbols)}"
    )
    for path in result.written:
        print(path)
    if result.skipped_symbols:
        print("Skipped symbols: " + ",".join(result.skipped_symbols))


def run_data_universe(args: argparse.Namespace) -> None:
    as_of_date = parse_date(args.as_of_date) if args.as_of_date else date.today()
    if as_of_date is None:
        raise ValueError("as-of-date is required")
    if args.min_listed_days < 0:
        raise ValueError("min-listed-days cannot be negative")
    if args.liquidity_window <= 0:
        raise ValueError("liquidity-window must be positive")
    filters = UniverseFilters(
        as_of_date=as_of_date,
        min_listed_days=args.min_listed_days,
        exchanges=parse_exchange_set(args.exchanges),
        exclude_bj=not args.include_bj,
        exclude_st=not args.include_st,
        include_industries=parse_csv_set(args.include_industries),
        exclude_industries=parse_csv_set(args.exclude_industries),
        daily_dir=Path(args.daily_dir),
        liquidity_window=args.liquidity_window,
        min_avg_amount=args.min_avg_amount,
    )
    result = build_universe_csv(
        stock_basic_path=Path(args.stock_basic),
        output_path=Path(args.output),
        filters=filters,
    )
    print(
        "Universe build complete. "
        f"stock_basic={args.stock_basic} output={result.path} as_of_date={as_of_date.isoformat()} "
        f"selected={len(result.symbols)} excluded={result.excluded_count} "
        f"min_avg_amount={args.min_avg_amount or 0:.2f}"
    )
    print(result.path)


def _resolve_start_date(start_date_arg: Optional[str], config: Optional[AppConfig]) -> date:
    parsed = parse_date(start_date_arg) if start_date_arg else None
    if parsed is not None:
        return parsed
    if config is not None and config.data.start_date is not None:
        return config.data.start_date
    raise ValueError("start-date is required unless config.data.start_date is set")


def _resolve_symbols(
    symbols_arg: Optional[str],
    symbols_file: Optional[str],
    config: Optional[AppConfig],
) -> List[str]:
    symbols: List[str] = []
    if symbols_arg:
        symbols.extend(_split_symbols(symbols_arg))
    if symbols_file:
        symbols.extend(_read_symbols_file(Path(symbols_file)))
    if not symbols and config is not None:
        symbols.extend(config.data.symbols)
    symbols = _dedupe_symbols(symbols)
    if not symbols:
        raise ValueError("symbols are required; use --symbols, --symbols-file, or config.data.symbols")
    return symbols


def _read_symbols_file(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as fh:
        text = fh.read()
    lines = [line for line in text.splitlines() if line.strip()]
    if lines and "," in lines[0]:
        header = [item.strip() for item in lines[0].split(",")]
        symbol_column = _symbol_column_index(header)
        if symbol_column is not None:
            symbols = []
            for line in lines[1:]:
                columns = [item.strip() for item in line.split(",")]
                if symbol_column < len(columns) and columns[symbol_column]:
                    symbols.append(columns[symbol_column])
            return symbols
    return _split_symbols(text)


def _symbol_column_index(header: List[str]) -> Optional[int]:
    for name in ("ts_code", "symbol"):
        if name in header:
            return header.index(name)
    return None


def _split_symbols(text: str) -> List[str]:
    normalized = text.replace("\n", ",").replace("\t", ",")
    symbols = []
    for item in normalized.split(","):
        symbol = item.strip()
        if symbol and not symbol.startswith("#"):
            symbols.append(symbol)
    return symbols


def _dedupe_symbols(symbols: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for symbol in symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(symbol)
    return deduped


def _optional_env(name: str) -> Optional[str]:
    value = os.environ.get(name, "").strip()
    return value or None


def _compact_error(error: str) -> str:
    text = " ".join(error.split())
    if len(text) > 180:
        return text[:177] + "..."
    return text


def load_portfolio(
    portfolio_path: Optional[str],
    default_cash: float,
) -> Tuple[float, Dict[str, Position]]:
    if not portfolio_path:
        return default_cash, {}
    path = Path(portfolio_path)
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    cash = float(raw.get("cash", default_cash))
    positions = {}
    for symbol, item in raw.get("positions", {}).items():
        entry_date = parse_date(item["entry_date"])
        if entry_date is None:
            raise ValueError(f"missing entry_date for {symbol}")
        positions[symbol] = Position(
            symbol=symbol,
            shares=int(item["shares"]),
            cost_basis=float(item["cost_basis"]),
            entry_date=entry_date,
            highest_close=float(item.get("highest_close", item["cost_basis"])),
            last_price=float(item.get("last_price", item["cost_basis"])),
        )
    return cash, positions


if __name__ == "__main__":
    main()
