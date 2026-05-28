import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from letsquant.config import parse_date
from letsquant.models import Action, ManualOrder


@dataclass(frozen=True)
class Fill:
    trade_date: date
    signal_date: date
    symbol: str
    action: Action
    shares: int
    price: float
    commission: float = 0.0
    stamp_tax: float = 0.0
    transfer_fee: float = 0.0
    note: str = ""

    @property
    def gross_value(self) -> float:
        return self.shares * self.price

    @property
    def total_costs(self) -> float:
        return self.commission + self.stamp_tax + self.transfer_fee


@dataclass(frozen=True)
class FillReconciliation:
    signal_date: date
    symbol: str
    action: Action
    planned_shares: int
    filled_shares: int
    reference_price: float
    avg_fill_price: float
    planned_value: float
    filled_value: float
    share_diff: int
    value_diff: float
    slippage_bps: float
    total_costs: float
    status: str
    note: str


@dataclass(frozen=True)
class ReplayPosition:
    symbol: str
    shares: int
    avg_cost: float
    realized_pnl: float


@dataclass(frozen=True)
class FillReplayResult:
    initial_cash: float
    cash: float
    positions: List[ReplayPosition]
    realized_pnl: float


def read_manual_orders(path: Path) -> List[ManualOrder]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [_manual_order_from_row(row) for row in csv.DictReader(fh)]


def read_fills(path: Path) -> List[Fill]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [_fill_from_row(row) for row in csv.DictReader(fh)]


def reconcile_fills(
    orders: Iterable[ManualOrder],
    fills: Iterable[Fill],
) -> List[FillReconciliation]:
    order_map = {_key(order.signal_date, order.symbol, order.action): order for order in orders}
    fills_by_key: Dict[Tuple[date, str, Action], List[Fill]] = {}
    for fill in fills:
        fills_by_key.setdefault(_key(fill.signal_date, fill.symbol, fill.action), []).append(fill)

    results: List[FillReconciliation] = []
    for key, order in sorted(order_map.items(), key=lambda item: (item[0][0], item[0][1], item[0][2].value)):
        matched = fills_by_key.pop(key, [])
        results.append(_reconcile_order(order, matched))

    for key, unmatched in sorted(fills_by_key.items(), key=lambda item: (item[0][0], item[0][1], item[0][2].value)):
        results.append(_reconcile_unplanned(key, unmatched))
    return results


def write_fill_reconciliation(path: Path, rows: Iterable[FillReconciliation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "signal_date",
        "symbol",
        "action",
        "status",
        "planned_shares",
        "filled_shares",
        "share_diff",
        "reference_price",
        "avg_fill_price",
        "planned_value",
        "filled_value",
        "value_diff",
        "slippage_bps",
        "total_costs",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "signal_date": row.signal_date.isoformat(),
                    "symbol": row.symbol,
                    "action": row.action.value,
                    "status": row.status,
                    "planned_shares": row.planned_shares,
                    "filled_shares": row.filled_shares,
                    "share_diff": row.share_diff,
                    "reference_price": f"{row.reference_price:.4f}",
                    "avg_fill_price": "" if row.avg_fill_price <= 0 else f"{row.avg_fill_price:.4f}",
                    "planned_value": f"{row.planned_value:.2f}",
                    "filled_value": f"{row.filled_value:.2f}",
                    "value_diff": f"{row.value_diff:.2f}",
                    "slippage_bps": f"{row.slippage_bps:.2f}",
                    "total_costs": f"{row.total_costs:.2f}",
                    "note": row.note,
                }
            )


def replay_fills(fills: Iterable[Fill], initial_cash: float) -> FillReplayResult:
    if initial_cash < 0:
        raise ValueError("initial_cash cannot be negative")
    cash = initial_cash
    positions: Dict[str, ReplayPosition] = {}
    realized_pnl = 0.0
    ordered = sorted(fills, key=lambda fill: (fill.trade_date, fill.symbol, fill.action.value))
    for fill in ordered:
        if fill.shares <= 0:
            raise ValueError(f"fill shares must be positive: {fill}")
        if fill.action == Action.BUY:
            cash -= fill.gross_value + fill.total_costs
            positions[fill.symbol] = _apply_buy(positions.get(fill.symbol), fill)
        elif fill.action == Action.SELL:
            position = positions.get(fill.symbol)
            if position is None or fill.shares > position.shares:
                raise ValueError(f"cannot sell {fill.shares} shares of {fill.symbol}; position is insufficient")
            cash += fill.gross_value - fill.total_costs
            sell_pnl = fill.gross_value - fill.total_costs - fill.shares * position.avg_cost
            realized_pnl += sell_pnl
            remaining = position.shares - fill.shares
            if remaining > 0:
                positions[fill.symbol] = ReplayPosition(
                    symbol=fill.symbol,
                    shares=remaining,
                    avg_cost=position.avg_cost,
                    realized_pnl=position.realized_pnl + sell_pnl,
                )
            else:
                positions.pop(fill.symbol)
        else:
            continue

    return FillReplayResult(
        initial_cash=initial_cash,
        cash=cash,
        positions=sorted(positions.values(), key=lambda item: item.symbol),
        realized_pnl=realized_pnl,
    )


def write_replay_positions(path: Path, result: FillReplayResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["symbol", "shares", "avg_cost", "market_value_at_cost", "realized_pnl"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for position in result.positions:
            writer.writerow(
                {
                    "symbol": position.symbol,
                    "shares": position.shares,
                    "avg_cost": f"{position.avg_cost:.4f}",
                    "market_value_at_cost": f"{position.shares * position.avg_cost:.2f}",
                    "realized_pnl": f"{position.realized_pnl:.2f}",
                }
            )


def write_replay_summary(path: Path, result: FillReplayResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["initial_cash", "cash", "position_count", "realized_pnl"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "initial_cash": f"{result.initial_cash:.2f}",
                "cash": f"{result.cash:.2f}",
                "position_count": len(result.positions),
                "realized_pnl": f"{result.realized_pnl:.2f}",
            }
        )


def _manual_order_from_row(row: Dict[str, str]) -> ManualOrder:
    signal_date = parse_date(row.get("signal_date"))
    if signal_date is None:
        raise ValueError(f"missing signal_date in manual order row: {row}")
    return ManualOrder(
        signal_date=signal_date,
        symbol=_required(row, "symbol"),
        action=Action(_required(row, "action")),
        shares=int(float(_required(row, "shares"))),
        reference_price=float(_required(row, "reference_price")),
        estimated_value=float(row.get("estimated_value") or 0),
        reason=row.get("reason", ""),
        note=row.get("note", ""),
    )


def _fill_from_row(row: Dict[str, str]) -> Fill:
    trade_date = parse_date(row.get("trade_date"))
    signal_date = parse_date(row.get("signal_date") or row.get("trade_date"))
    if trade_date is None or signal_date is None:
        raise ValueError(f"missing trade_date/signal_date in fill row: {row}")
    return Fill(
        trade_date=trade_date,
        signal_date=signal_date,
        symbol=_required(row, "symbol"),
        action=Action(_required(row, "action")),
        shares=int(float(_required(row, "shares"))),
        price=float(_required(row, "price")),
        commission=float(row.get("commission") or 0),
        stamp_tax=float(row.get("stamp_tax") or 0),
        transfer_fee=float(row.get("transfer_fee") or 0),
        note=row.get("note", ""),
    )


def _apply_buy(position: ReplayPosition | None, fill: Fill) -> ReplayPosition:
    if position is None:
        return ReplayPosition(
            symbol=fill.symbol,
            shares=fill.shares,
            avg_cost=(fill.gross_value + fill.total_costs) / fill.shares,
            realized_pnl=0.0,
        )
    total_shares = position.shares + fill.shares
    total_cost = position.shares * position.avg_cost + fill.gross_value + fill.total_costs
    return ReplayPosition(
        symbol=fill.symbol,
        shares=total_shares,
        avg_cost=total_cost / total_shares,
        realized_pnl=position.realized_pnl,
    )


def _reconcile_order(order: ManualOrder, fills: List[Fill]) -> FillReconciliation:
    filled_shares = sum(fill.shares for fill in fills)
    filled_value = sum(fill.gross_value for fill in fills)
    total_costs = sum(fill.total_costs for fill in fills)
    avg_price = filled_value / filled_shares if filled_shares > 0 else 0.0
    slippage = _slippage_bps(order.action, order.reference_price, avg_price) if avg_price > 0 else 0.0
    status = _fill_status(order.shares, filled_shares)
    return FillReconciliation(
        signal_date=order.signal_date,
        symbol=order.symbol,
        action=order.action,
        planned_shares=order.shares,
        filled_shares=filled_shares,
        reference_price=order.reference_price,
        avg_fill_price=avg_price,
        planned_value=order.shares * order.reference_price,
        filled_value=filled_value,
        share_diff=filled_shares - order.shares,
        value_diff=filled_value - order.shares * order.reference_price,
        slippage_bps=slippage,
        total_costs=total_costs,
        status=status,
        note="; ".join(fill.note for fill in fills if fill.note),
    )


def _reconcile_unplanned(
    key: Tuple[date, str, Action],
    fills: List[Fill],
) -> FillReconciliation:
    signal_date, symbol, action = key
    filled_shares = sum(fill.shares for fill in fills)
    filled_value = sum(fill.gross_value for fill in fills)
    total_costs = sum(fill.total_costs for fill in fills)
    avg_price = filled_value / filled_shares if filled_shares > 0 else 0.0
    return FillReconciliation(
        signal_date=signal_date,
        symbol=symbol,
        action=action,
        planned_shares=0,
        filled_shares=filled_shares,
        reference_price=0.0,
        avg_fill_price=avg_price,
        planned_value=0.0,
        filled_value=filled_value,
        share_diff=filled_shares,
        value_diff=filled_value,
        slippage_bps=0.0,
        total_costs=total_costs,
        status="unplanned",
        note="; ".join(fill.note for fill in fills if fill.note),
    )


def _fill_status(planned_shares: int, filled_shares: int) -> str:
    if filled_shares <= 0:
        return "not_filled"
    if filled_shares < planned_shares:
        return "partial"
    if filled_shares == planned_shares:
        return "filled"
    return "overfilled"


def _slippage_bps(action: Action, reference_price: float, fill_price: float) -> float:
    if reference_price <= 0:
        return 0.0
    raw = fill_price / reference_price - 1
    if action == Action.SELL:
        raw *= -1
    return raw * 10000


def _key(signal_date: date, symbol: str, action: Action) -> Tuple[date, str, Action]:
    return (signal_date, symbol, action)


def _required(row: Dict[str, str], name: str) -> str:
    value = row.get(name, "").strip()
    if not value:
        raise ValueError(f"missing {name} in row: {row}")
    return value
