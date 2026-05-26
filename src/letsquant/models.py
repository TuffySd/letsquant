from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Bar:
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError(f"prices must be positive for {self.symbol} {self.date}")
        if self.low > self.high:
            raise ValueError(f"low cannot exceed high for {self.symbol} {self.date}")
        if self.open > self.high or self.open < self.low:
            raise ValueError(f"open is outside high/low for {self.symbol} {self.date}")
        if self.close > self.high or self.close < self.low:
            raise ValueError(f"close is outside high/low for {self.symbol} {self.date}")


@dataclass
class Position:
    symbol: str
    shares: int
    cost_basis: float
    entry_date: date
    highest_close: float
    last_price: float

    @property
    def market_value(self) -> float:
        return self.shares * self.last_price

    def mark(self, close: float) -> None:
        self.last_price = close
        if close > self.highest_close:
            self.highest_close = close


@dataclass(frozen=True)
class Signal:
    signal_date: date
    symbol: str
    action: Action
    reason: str
    confidence: float = 1.0
    reference_price: Optional[float] = None


@dataclass(frozen=True)
class Trade:
    trade_date: date
    symbol: str
    action: Action
    shares: int
    price: float
    gross_value: float
    commission: float
    stamp_tax: float
    transfer_fee: float
    cash_flow: float
    pnl: float = 0.0
    reason: str = ""

    @property
    def total_costs(self) -> float:
        return self.commission + self.stamp_tax + self.transfer_fee


@dataclass(frozen=True)
class PortfolioSnapshot:
    date: date
    cash: float
    market_value: float
    equity: float
    positions: int
    drawdown: float


@dataclass(frozen=True)
class ManualOrder:
    signal_date: date
    symbol: str
    action: Action
    shares: int
    reference_price: float
    estimated_value: float
    reason: str
    note: str
