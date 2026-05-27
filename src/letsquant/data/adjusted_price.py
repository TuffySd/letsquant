import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


PRICE_FIELDS = ("open", "high", "low", "close", "pre_close", "limit_up", "limit_down")


@dataclass(frozen=True)
class AdjustedPriceResult:
    written: List[Path]
    skipped_symbols: List[str]


def build_adjusted_daily_csv(
    symbols: Iterable[str],
    daily_dir: Path,
    adj_factor_dir: Path,
    output_dir: Path,
    mode: str = "qfq",
) -> AdjustedPriceResult:
    if mode not in ("qfq", "hfq"):
        raise ValueError("mode must be qfq or hfq")

    daily_dir = Path(daily_dir)
    adj_factor_dir = Path(adj_factor_dir)
    output_dir = Path(output_dir)
    written: List[Path] = []
    skipped_symbols: List[str] = []

    for symbol in symbols:
        daily_path = daily_dir / f"{symbol}.csv"
        factor_path = adj_factor_dir / f"{symbol}.csv"
        if not daily_path.exists() or not factor_path.exists():
            skipped_symbols.append(symbol)
            continue

        daily_rows = _read_rows(daily_path)
        factors = _read_factors(factor_path)
        adjusted_rows = _adjust_rows(daily_rows, factors, mode)
        if not adjusted_rows:
            skipped_symbols.append(symbol)
            continue

        output_path = output_dir / f"{symbol}.csv"
        _write_rows(output_path, adjusted_rows)
        written.append(output_path)

    return AdjustedPriceResult(written=written, skipped_symbols=skipped_symbols)


def _adjust_rows(
    daily_rows: List[Dict[str, str]],
    factors: Dict[str, float],
    mode: str,
) -> List[Dict[str, str]]:
    rows_with_factors = [row for row in daily_rows if row.get("trade_date") in factors]
    if not rows_with_factors:
        return []

    latest_factor = factors[str(rows_with_factors[-1]["trade_date"])]
    adjusted_rows: List[Dict[str, str]] = []
    for row in rows_with_factors:
        trade_date = str(row["trade_date"])
        factor = factors[trade_date]
        ratio = factor / latest_factor if mode == "qfq" else factor
        adjusted = dict(row)
        for field in PRICE_FIELDS:
            if row.get(field) not in (None, ""):
                adjusted[field] = _format_float(float(row[field]) * ratio)
        adjusted["adj_factor"] = _format_float(factor)
        adjusted["adjustment"] = mode
        adjusted_rows.append(adjusted)
    return adjusted_rows


def _read_factors(path: Path) -> Dict[str, float]:
    factors: Dict[str, float] = {}
    for row in _read_rows(path):
        trade_date = row.get("trade_date")
        factor = row.get("adj_factor")
        if trade_date and factor not in (None, ""):
            factors[str(trade_date)] = float(factor)
    return factors


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fieldnames(rows: List[Dict[str, str]]) -> List[str]:
    names: List[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    return names


def _format_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")
