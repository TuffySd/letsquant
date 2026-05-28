import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DataConfig:
    source: str
    data_dir: Path
    symbols: List[str]
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass(frozen=True)
class RiskConfig:
    max_position_pct: float = 0.2
    max_positions: int = 5
    cash_reserve_pct: float = 0.05
    lot_size: int = 100


@dataclass(frozen=True)
class CostConfig:
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    slippage_bps: float = 5.0


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkConfig:
    symbol: str
    data_dir: Path


@dataclass(frozen=True)
class AppConfig:
    initial_cash: float
    data: DataConfig
    strategy: StrategyConfig
    risk: RiskConfig
    costs: CostConfig
    output_dir: Path
    benchmark: Optional[BenchmarkConfig] = None


def parse_date(value: Optional[str]) -> Optional[date]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def load_config(path: str) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    data_raw = raw["data"]
    strategy_raw = raw["strategy"]
    risk_raw = raw.get("risk", {})
    costs_raw = raw.get("costs", {})
    benchmark_raw = raw.get("benchmark")
    benchmark = None
    if benchmark_raw:
        symbol = str(benchmark_raw.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("benchmark.symbol is required when benchmark is configured")
        benchmark = BenchmarkConfig(
            symbol=symbol,
            data_dir=Path(benchmark_raw.get("data_dir", "data/index_daily")),
        )

    return AppConfig(
        initial_cash=float(raw.get("initial_cash", 100000)),
        data=DataConfig(
            source=data_raw.get("source", "csv"),
            data_dir=Path(data_raw.get("data_dir", "data/daily")),
            symbols=list(data_raw.get("symbols", [])),
            start_date=parse_date(data_raw.get("start_date")),
            end_date=parse_date(data_raw.get("end_date")),
        ),
        strategy=StrategyConfig(
            name=strategy_raw.get("name", "trend_breakout"),
            params=dict(strategy_raw.get("params", {})),
        ),
        risk=RiskConfig(
            max_position_pct=float(risk_raw.get("max_position_pct", 0.2)),
            max_positions=int(risk_raw.get("max_positions", 5)),
            cash_reserve_pct=float(risk_raw.get("cash_reserve_pct", 0.05)),
            lot_size=int(risk_raw.get("lot_size", 100)),
        ),
        costs=CostConfig(
            commission_rate=float(costs_raw.get("commission_rate", 0.0003)),
            min_commission=float(costs_raw.get("min_commission", 5)),
            stamp_tax_rate=float(costs_raw.get("stamp_tax_rate", 0.0005)),
            transfer_fee_rate=float(costs_raw.get("transfer_fee_rate", 0.00001)),
            slippage_bps=float(costs_raw.get("slippage_bps", 5)),
        ),
        output_dir=Path(raw.get("output_dir", "results")),
        benchmark=benchmark,
    )
