import csv
import json
from pathlib import Path
from typing import Dict, Iterable

from letsquant.models import ManualOrder, PortfolioSnapshot, Signal, Trade


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_metrics(path: Path, metrics: Dict[str, float]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)


def write_trades(path: Path, trades: Iterable[Trade]) -> None:
    fieldnames = [
        "trade_date",
        "symbol",
        "action",
        "shares",
        "price",
        "gross_value",
        "commission",
        "stamp_tax",
        "transfer_fee",
        "cash_flow",
        "pnl",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            writer.writerow(
                {
                    "trade_date": trade.trade_date.isoformat(),
                    "symbol": trade.symbol,
                    "action": trade.action.value,
                    "shares": trade.shares,
                    "price": f"{trade.price:.4f}",
                    "gross_value": f"{trade.gross_value:.2f}",
                    "commission": f"{trade.commission:.2f}",
                    "stamp_tax": f"{trade.stamp_tax:.2f}",
                    "transfer_fee": f"{trade.transfer_fee:.2f}",
                    "cash_flow": f"{trade.cash_flow:.2f}",
                    "pnl": f"{trade.pnl:.2f}",
                    "reason": trade.reason,
                }
            )


def write_signals(path: Path, signals: Iterable[Signal]) -> None:
    fieldnames = ["signal_date", "symbol", "action", "reference_price", "confidence", "reason"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for signal in signals:
            writer.writerow(
                {
                    "signal_date": signal.signal_date.isoformat(),
                    "symbol": signal.symbol,
                    "action": signal.action.value,
                    "reference_price": "" if signal.reference_price is None else f"{signal.reference_price:.4f}",
                    "confidence": f"{signal.confidence:.2f}",
                    "reason": signal.reason,
                }
            )


def write_equity_curve(path: Path, snapshots: Iterable[PortfolioSnapshot]) -> None:
    fieldnames = ["date", "cash", "market_value", "equity", "positions", "drawdown"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for snapshot in snapshots:
            writer.writerow(
                {
                    "date": snapshot.date.isoformat(),
                    "cash": f"{snapshot.cash:.2f}",
                    "market_value": f"{snapshot.market_value:.2f}",
                    "equity": f"{snapshot.equity:.2f}",
                    "positions": snapshot.positions,
                    "drawdown": f"{snapshot.drawdown:.4f}",
                }
            )


def write_manual_orders(path: Path, orders: Iterable[ManualOrder]) -> None:
    fieldnames = [
        "signal_date",
        "symbol",
        "action",
        "shares",
        "reference_price",
        "estimated_value",
        "reason",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for order in orders:
            writer.writerow(
                {
                    "signal_date": order.signal_date.isoformat(),
                    "symbol": order.symbol,
                    "action": order.action.value,
                    "shares": order.shares,
                    "reference_price": f"{order.reference_price:.4f}",
                    "estimated_value": f"{order.estimated_value:.2f}",
                    "reason": order.reason,
                    "note": order.note,
                }
            )
