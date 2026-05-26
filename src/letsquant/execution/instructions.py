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
        if signal.action == Action.BUY:
            shares = _buy_shares(price, cash, equity, positions, risk, costs)
            note = "next trading day manual buy; recheck limit-up, suspension, and news before order"
        elif signal.action == Action.SELL:
            shares = positions.get(signal.symbol).shares if signal.symbol in positions else 0
            note = "next trading day manual sell; recheck limit-down, suspension, and news before order"
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
    bars = bars_by_symbol.get(symbol)
    if not bars:
        raise ValueError(f"missing latest price for {symbol}")
    return bars[-1].close
