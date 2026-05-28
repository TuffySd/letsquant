from typing import Dict, Iterable, List

from letsquant.config import CostConfig, RiskConfig
from letsquant.models import Action, Bar, ManualOrder, Position, Signal


def build_manual_orders(
    signals: Iterable[Signal],
    bars_by_symbol: Dict[str, List[Bar]],
    cash: float,
    positions: Dict[str, Position],
    risk: RiskConfig,
    costs: CostConfig,
) -> List[ManualOrder]:
    orders: List[ManualOrder] = []
    equity = cash + sum(_latest_price(symbol, bars_by_symbol) * pos.shares for symbol, pos in positions.items())
    for signal in signals:
        price = signal.reference_price or _latest_price(signal.symbol, bars_by_symbol)
        latest_bar = _latest_bar(signal.symbol, bars_by_symbol)
        if signal.action == Action.BUY:
            shares = _buy_shares(price, cash, equity, positions, risk, costs)
            note = _review_note(signal.action, latest_bar)
        elif signal.action == Action.SELL:
            shares = positions.get(signal.symbol).shares if signal.symbol in positions else 0
            note = _review_note(signal.action, latest_bar)
        else:
            continue
        if shares <= 0:
            continue
        orders.append(
            ManualOrder(
                signal_date=signal.signal_date,
                symbol=signal.symbol,
                action=signal.action,
                shares=shares,
                reference_price=price,
                estimated_value=shares * price,
                reason=signal.reason,
                note=note,
            )
        )
    return orders


def _buy_shares(
    price: float,
    cash: float,
    equity: float,
    positions: Dict[str, Position],
    risk: RiskConfig,
    costs: CostConfig,
) -> int:
    if len(positions) >= risk.max_positions:
        return 0
    reserve_cash = equity * risk.cash_reserve_pct
    deployable_cash = max(0.0, cash - reserve_cash)
    target_cash = min(deployable_cash, equity * risk.max_position_pct)
    estimated_price = price * (1 + costs.slippage_bps / 10000)
    if estimated_price <= 0:
        return 0
    raw_shares = int(target_cash / estimated_price)
    return raw_shares // risk.lot_size * risk.lot_size


def _latest_price(symbol: str, bars_by_symbol: Dict[str, List[Bar]]) -> float:
    return _latest_bar(symbol, bars_by_symbol).close


def _latest_bar(symbol: str, bars_by_symbol: Dict[str, List[Bar]]) -> Bar:
    bars = bars_by_symbol.get(symbol)
    if not bars:
        raise ValueError(f"missing latest price for {symbol}")
    return bars[-1]


def _review_note(action: Action, latest_bar: Bar) -> str:
    checks = [
        "verify next trading day tradability before order",
        f"latest_date={latest_bar.date.isoformat()}",
        f"latest_suspended={'yes' if latest_bar.is_suspended else 'no'}",
    ]
    if action == Action.BUY:
        at_limit_up = _at_price_limit(latest_bar.close, latest_bar.limit_up)
        checks.append(f"latest_close_at_limit_up={'yes' if at_limit_up else 'no'}")
    elif action == Action.SELL:
        at_limit_down = _at_price_limit(latest_bar.close, latest_bar.limit_down)
        checks.append(f"latest_close_at_limit_down={'yes' if at_limit_down else 'no'}")
    checks.extend(
        [
            "review major announcements",
            "review news",
            "review earnings calendar",
        ]
    )
    return "; ".join(checks)


def _at_price_limit(price: float, limit_price: float | None) -> bool:
    if limit_price is None:
        return False
    return abs(price - limit_price) <= 0.0001
