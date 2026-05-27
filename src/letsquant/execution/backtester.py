import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional

from letsquant.config import CostConfig, RiskConfig
from letsquant.indicators import max_drawdown
from letsquant.models import Action, Bar, OrderRejection, PortfolioSnapshot, Position, Signal, Trade
from letsquant.strategies.base import Strategy


@dataclass
class BacktestResult:
    trades: List[Trade]
    signals: List[Signal]
    snapshots: List[PortfolioSnapshot]
    pending_orders: List[Signal]
    order_rejections: List[OrderRejection]
    metrics: Dict[str, float]


class Backtester:
    def __init__(
        self,
        strategy: Strategy,
        initial_cash: float,
        risk: RiskConfig,
        costs: CostConfig,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.risk = risk
        self.costs = costs

    def run(self, bars_by_symbol: Dict[str, List[Bar]]) -> BacktestResult:
        cash = self.initial_cash
        positions: Dict[str, Position] = {}
        trades: List[Trade] = []
        signals: List[Signal] = []
        pending_orders: List[Signal] = []
        order_rejections: List[OrderRejection] = []
        snapshots: List[PortfolioSnapshot] = []
        latest_close: Dict[str, float] = {}
        peak_equity = self.initial_cash

        bars_by_date = self._index_by_date(bars_by_symbol)
        histories: Dict[str, List[Bar]] = {symbol: [] for symbol in bars_by_symbol}

        for current_date in sorted(bars_by_date):
            day_bars = bars_by_date[current_date]

            cash = self._execute_pending(
                current_date,
                pending_orders,
                day_bars,
                positions,
                latest_close,
                cash,
                trades,
                order_rejections,
            )
            pending_orders = [
                signal for signal in pending_orders if signal.symbol not in day_bars
            ]

            for symbol, bar in day_bars.items():
                histories.setdefault(symbol, []).append(bar)
                latest_close[symbol] = bar.close
                if symbol in positions:
                    positions[symbol].mark(bar.close)

            equity = self._equity(cash, positions, latest_close)
            peak_equity = max(peak_equity, equity)
            drawdown = equity / peak_equity - 1 if peak_equity else 0.0
            snapshots.append(
                PortfolioSnapshot(
                    date=current_date,
                    cash=cash,
                    market_value=sum(pos.market_value for pos in positions.values()),
                    equity=equity,
                    positions=len(positions),
                    drawdown=drawdown,
                )
            )

            for symbol in sorted(day_bars):
                has_pending = any(signal.symbol == symbol for signal in pending_orders)
                if has_pending:
                    continue
                signal = self.strategy.generate(symbol, histories[symbol], positions.get(symbol))
                if signal.action != Action.HOLD:
                    signals.append(signal)
                    pending_orders.append(signal)

        metrics = self._metrics(snapshots, trades)
        metrics["order_rejection_count"] = float(len(order_rejections))
        return BacktestResult(trades, signals, snapshots, pending_orders, order_rejections, metrics)

    def _execute_pending(
        self,
        current_date: date,
        pending_orders: Iterable[Signal],
        day_bars: Dict[str, Bar],
        positions: Dict[str, Position],
        latest_close: Dict[str, float],
        cash: float,
        trades: List[Trade],
        order_rejections: List[OrderRejection],
    ) -> float:
        for signal in list(pending_orders):
            bar = day_bars.get(signal.symbol)
            if bar is None:
                continue

            rejection_reason = self._trade_rejection_reason(signal.action, bar)
            if rejection_reason is not None:
                order_rejections.append(
                    OrderRejection(
                        trade_date=current_date,
                        symbol=signal.symbol,
                        action=signal.action,
                        reason=rejection_reason,
                        signal_reason=signal.reason,
                        reference_price=signal.reference_price,
                    )
                )
                continue

            if signal.action == Action.BUY:
                if signal.symbol in positions:
                    continue
                if len(positions) >= self.risk.max_positions:
                    continue
                trade = self._buy(current_date, signal, bar, positions, latest_close, cash)
                if trade is None:
                    continue
                cash += trade.cash_flow
                trades.append(trade)
            elif signal.action == Action.SELL:
                position = positions.get(signal.symbol)
                if position is None:
                    continue
                trade = self._sell(current_date, signal, bar, position)
                cash += trade.cash_flow
                trades.append(trade)
                del positions[signal.symbol]
        return cash

    def _buy(
        self,
        current_date: date,
        signal: Signal,
        bar: Bar,
        positions: Dict[str, Position],
        latest_close: Dict[str, float],
        cash: float,
    ) -> Optional[Trade]:
        equity = self._equity(cash, positions, latest_close)
        reserve_cash = equity * self.risk.cash_reserve_pct
        deployable_cash = max(0.0, cash - reserve_cash)
        target_cash = min(deployable_cash, equity * self.risk.max_position_pct)
        price = self._slipped_price(bar.open, Action.BUY)
        if target_cash <= price * self.risk.lot_size:
            return None

        estimated_shares = int(target_cash / price)
        shares = self._round_lot(estimated_shares)
        while shares >= self.risk.lot_size:
            gross = shares * price
            commission = self._commission(gross)
            transfer_fee = gross * self.costs.transfer_fee_rate
            total_cash_needed = gross + commission + transfer_fee
            if total_cash_needed <= deployable_cash:
                position = Position(
                    symbol=signal.symbol,
                    shares=shares,
                    cost_basis=price,
                    entry_date=current_date,
                    highest_close=bar.close,
                    last_price=bar.close,
                )
                positions[signal.symbol] = position
                return Trade(
                    trade_date=current_date,
                    symbol=signal.symbol,
                    action=Action.BUY,
                    shares=shares,
                    price=price,
                    gross_value=gross,
                    commission=commission,
                    stamp_tax=0.0,
                    transfer_fee=transfer_fee,
                    cash_flow=-total_cash_needed,
                    reason=signal.reason,
                )
            shares -= self.risk.lot_size
        return None

    def _sell(
        self,
        current_date: date,
        signal: Signal,
        bar: Bar,
        position: Position,
    ) -> Trade:
        price = self._slipped_price(bar.open, Action.SELL)
        gross = position.shares * price
        commission = self._commission(gross)
        stamp_tax = gross * self.costs.stamp_tax_rate
        transfer_fee = gross * self.costs.transfer_fee_rate
        cash_flow = gross - commission - stamp_tax - transfer_fee
        pnl = cash_flow - position.shares * position.cost_basis
        return Trade(
            trade_date=current_date,
            symbol=signal.symbol,
            action=Action.SELL,
            shares=position.shares,
            price=price,
            gross_value=gross,
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            cash_flow=cash_flow,
            pnl=pnl,
            reason=signal.reason,
        )

    def _metrics(
        self,
        snapshots: List[PortfolioSnapshot],
        trades: List[Trade],
    ) -> Dict[str, float]:
        if not snapshots:
            return {
                "initial_cash": self.initial_cash,
                "final_equity": self.initial_cash,
                "total_return": 0.0,
                "annualized_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe": 0.0,
                "trade_count": 0.0,
                "win_rate": 0.0,
            }

        equities = [snapshot.equity for snapshot in snapshots]
        returns = [
            equities[index] / equities[index - 1] - 1
            for index in range(1, len(equities))
            if equities[index - 1] > 0
        ]
        final_equity = equities[-1]
        total_return = final_equity / self.initial_cash - 1
        days = max(1, (snapshots[-1].date - snapshots[0].date).days)
        annualized_return = (final_equity / self.initial_cash) ** (365 / days) - 1
        sharpe = 0.0
        if len(returns) > 1 and statistics.pstdev(returns) > 0:
            sharpe = statistics.mean(returns) / statistics.pstdev(returns) * math.sqrt(252)
        sell_trades = [trade for trade in trades if trade.action == Action.SELL]
        wins = [trade for trade in sell_trades if trade.pnl > 0]

        return {
            "initial_cash": self.initial_cash,
            "final_equity": final_equity,
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown(equities),
            "sharpe": sharpe,
            "trade_count": float(len(trades)),
            "sell_count": float(len(sell_trades)),
            "win_rate": len(wins) / len(sell_trades) if sell_trades else 0.0,
        }

    def _equity(
        self,
        cash: float,
        positions: Dict[str, Position],
        latest_close: Dict[str, float],
    ) -> float:
        value = cash
        for symbol, position in positions.items():
            value += position.shares * latest_close.get(symbol, position.last_price)
        return value

    def _slipped_price(self, price: float, action: Action) -> float:
        rate = self.costs.slippage_bps / 10000
        if action == Action.BUY:
            return price * (1 + rate)
        if action == Action.SELL:
            return price * (1 - rate)
        return price

    def _commission(self, gross_value: float) -> float:
        if gross_value <= 0:
            return 0.0
        return max(gross_value * self.costs.commission_rate, self.costs.min_commission)

    def _round_lot(self, shares: int) -> int:
        if self.risk.lot_size <= 0:
            return shares
        return shares // self.risk.lot_size * self.risk.lot_size

    @staticmethod
    def _trade_rejection_reason(action: Action, bar: Bar) -> Optional[str]:
        tolerance = 1e-8
        if bar.is_suspended:
            return "suspended"
        if action == Action.BUY and bar.limit_up is not None and bar.open >= bar.limit_up - tolerance:
            return "limit_up"
        if action == Action.SELL and bar.limit_down is not None and bar.open <= bar.limit_down + tolerance:
            return "limit_down"
        return None

    @staticmethod
    def _index_by_date(bars_by_symbol: Dict[str, List[Bar]]) -> Dict[date, Dict[str, Bar]]:
        bars_by_date: Dict[date, Dict[str, Bar]] = {}
        for symbol, bars in bars_by_symbol.items():
            for bar in bars:
                bars_by_date.setdefault(bar.date, {})[symbol] = bar
        return bars_by_date
