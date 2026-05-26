from typing import List, Optional

from letsquant.indicators import rate_of_change, sma
from letsquant.models import Action, Bar, Position, Signal
from letsquant.strategies.base import Strategy


class TrendBreakoutStrategy(Strategy):
    """Medium-term A-share trend breakout strategy."""

    def __init__(
        self,
        short_window: int = 20,
        mid_window: int = 60,
        long_window: int = 120,
        breakout_window: int = 55,
        momentum_window: int = 60,
        min_momentum: float = 0.05,
        volume_window: int = 20,
        min_volume_ratio: float = 1.0,
        stop_loss_pct: float = 0.08,
        trailing_stop_pct: float = 0.15,
        max_holding_days: int = 90,
    ) -> None:
        self.short_window = short_window
        self.mid_window = mid_window
        self.long_window = long_window
        self.breakout_window = breakout_window
        self.momentum_window = momentum_window
        self.min_momentum = min_momentum
        self.volume_window = volume_window
        self.min_volume_ratio = min_volume_ratio
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_holding_days = max_holding_days
        self.min_bars = max(long_window, breakout_window + 1, momentum_window + 1, volume_window)

    def generate(
        self,
        symbol: str,
        history: List[Bar],
        position: Optional[Position],
    ) -> Signal:
        current = history[-1]
        if len(history) < self.min_bars:
            return self._hold(current, "insufficient_history")

        closes = [bar.close for bar in history]
        volumes = [bar.volume for bar in history]
        ma_short = sma(closes, self.short_window)
        ma_mid = sma(closes, self.mid_window)
        ma_long = sma(closes, self.long_window)
        momentum = rate_of_change(closes, self.momentum_window)

        if ma_short is None or ma_mid is None or ma_long is None or momentum is None:
            return self._hold(current, "indicator_not_ready")

        if position:
            return self._exit_signal(current, position, ma_mid)

        prior_high = max(bar.high for bar in history[-self.breakout_window - 1 : -1])
        avg_volume = sum(volumes[-self.volume_window:]) / self.volume_window
        trend_ok = ma_short > ma_mid > ma_long
        breakout_ok = current.close > prior_high
        momentum_ok = momentum >= self.min_momentum
        volume_ok = avg_volume <= 0 or current.volume >= avg_volume * self.min_volume_ratio

        if trend_ok and breakout_ok and momentum_ok and volume_ok:
            reason = (
                "trend_breakout:"
                f" close={current.close:.2f} prior_high={prior_high:.2f}"
                f" ma={ma_short:.2f}/{ma_mid:.2f}/{ma_long:.2f}"
                f" momentum={momentum:.2%}"
            )
            return Signal(current.date, symbol, Action.BUY, reason, 1.0, current.close)

        return self._hold(current, "no_entry")

    def _exit_signal(self, current: Bar, position: Position, ma_mid: float) -> Signal:
        held_days = (current.date - position.entry_date).days
        if current.close <= position.cost_basis * (1 - self.stop_loss_pct):
            return Signal(
                current.date,
                current.symbol,
                Action.SELL,
                f"stop_loss: close={current.close:.2f} cost={position.cost_basis:.2f}",
                1.0,
                current.close,
            )
        if current.close <= position.highest_close * (1 - self.trailing_stop_pct):
            return Signal(
                current.date,
                current.symbol,
                Action.SELL,
                f"trailing_stop: close={current.close:.2f} high_close={position.highest_close:.2f}",
                1.0,
                current.close,
            )
        if current.close < ma_mid:
            return Signal(
                current.date,
                current.symbol,
                Action.SELL,
                f"mid_ma_break: close={current.close:.2f} ma_mid={ma_mid:.2f}",
                1.0,
                current.close,
            )
        if self.max_holding_days > 0 and held_days >= self.max_holding_days:
            return Signal(
                current.date,
                current.symbol,
                Action.SELL,
                f"max_holding_days: held_days={held_days}",
                0.8,
                current.close,
            )
        return self._hold(current, "hold_position")

    @staticmethod
    def _hold(current: Bar, reason: str) -> Signal:
        return Signal(current.date, current.symbol, Action.HOLD, reason, 0.0, current.close)
