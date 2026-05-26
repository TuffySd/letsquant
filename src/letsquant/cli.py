import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from letsquant.config import AppConfig, load_config, parse_date
from letsquant.data import CsvBarSource
from letsquant.data.tushare_source import TushareDailySource
from letsquant.execution import Backtester
from letsquant.execution.instructions import build_manual_orders
from letsquant.models import Action, Bar, Position, Signal
from letsquant.reports import (
    ensure_output_dir,
    write_equity_curve,
    write_metrics,
    write_manual_orders,
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
        "--token-env",
        default="TUSHARE_TOKEN",
        help="environment variable containing the Tushare token",
    )

    args = parser.parse_args()

    if args.command == "backtest":
        config = load_config(args.config)
        run_backtest(config)
    elif args.command == "signal":
        config = load_config(args.config)
        run_signal(config, args.portfolio)
    elif args.command == "data" and args.data_command == "sync":
        run_data_sync(args)


def run_backtest(config: AppConfig) -> None:
    bars_by_symbol = load_bars(config)
    strategy = build_strategy(config.strategy.name, config.strategy.params)
    backtester = Backtester(strategy, config.initial_cash, config.risk, config.costs)
    result = backtester.run(bars_by_symbol)

    output_dir = ensure_output_dir(config.output_dir)
    write_metrics(output_dir / "metrics.json", result.metrics)
    write_trades(output_dir / "trades.csv", result.trades)
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

    source = TushareDailySource(token=token, cache_dir=cache_dir)
    result = source.sync_daily_csv(symbols, start_date, end_date)
    print(
        "Data sync complete. "
        f"provider={args.provider} cache_dir={cache_dir} "
        f"requested={len(symbols)} written={len(result.written)} empty={len(result.empty_symbols)}"
    )
    for path in result.written:
        print(path)
    if result.empty_symbols:
        print("Empty symbols: " + ",".join(result.empty_symbols))


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
        return _split_symbols(fh.read())


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
