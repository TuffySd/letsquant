import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from letsquant.config import AppConfig, load_config, parse_date
from letsquant.data import CsvBarSource
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

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "backtest":
        run_backtest(config)
    elif args.command == "signal":
        run_signal(config, args.portfolio)


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
