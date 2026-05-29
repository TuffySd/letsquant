import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional, Set

from letsquant.config import parse_date


@dataclass(frozen=True)
class UniverseResult:
    path: Path
    symbols: List[str]
    excluded_count: int


@dataclass(frozen=True)
class UniverseFilters:
    as_of_date: date
    min_listed_days: int = 180
    exchanges: Optional[Set[str]] = None
    exclude_bj: bool = True
    exclude_st: bool = True
    include_industries: Optional[Set[str]] = None
    exclude_industries: Optional[Set[str]] = None
    daily_dir: Optional[Path] = None
    liquidity_window: int = 20
    min_avg_amount: Optional[float] = None
    sort_by: str = "code"
    limit: Optional[int] = None


def build_universe_csv(
    stock_basic_path: Path,
    output_path: Path,
    filters: UniverseFilters,
) -> UniverseResult:
    rows = _read_rows(Path(stock_basic_path))
    selected = []
    excluded_count = 0
    for row in rows:
        if _include_stock(row, filters):
            selected.append(row)
        else:
            excluded_count += 1

    _sort_selected(selected, filters.sort_by)
    if filters.limit is not None:
        if filters.limit <= 0:
            raise ValueError("limit must be positive")
        selected = selected[: filters.limit]
    _write_rows(Path(output_path), selected)
    symbols = [str(row["ts_code"]) for row in selected]
    return UniverseResult(path=Path(output_path), symbols=symbols, excluded_count=excluded_count)


def _include_stock(row: dict[str, str], filters: UniverseFilters) -> bool:
    ts_code = str(row.get("ts_code", "")).strip()
    if not ts_code:
        return False

    exchange = _exchange_from_ts_code(ts_code)
    if filters.exchanges is not None and exchange not in filters.exchanges:
        return False
    if filters.exclude_bj and exchange == "BJ":
        return False
    if filters.exclude_st and _is_st_name(str(row.get("name", ""))):
        return False

    industry = str(row.get("industry", "")).strip()
    if filters.include_industries is not None and industry not in filters.include_industries:
        return False
    if filters.exclude_industries is not None and industry in filters.exclude_industries:
        return False

    list_date = parse_date(row.get("list_date"))
    if list_date is None:
        return False
    listed_days = (filters.as_of_date - list_date).days
    if listed_days < filters.min_listed_days:
        return False

    if filters.min_avg_amount is not None or filters.sort_by == "avg_amount":
        if filters.daily_dir is None:
            raise ValueError("daily_dir is required when liquidity filtering or sorting is enabled")
        avg_amount = _average_amount(
            filters.daily_dir / f"{ts_code}.csv",
            filters.as_of_date,
            filters.liquidity_window,
        )
        if avg_amount is None:
            return False
        row["avg_amount"] = f"{avg_amount:.2f}"
        if filters.min_avg_amount is not None and avg_amount < filters.min_avg_amount:
            return False

    return True


def _sort_selected(rows: List[dict[str, str]], sort_by: str) -> None:
    if sort_by == "code":
        rows.sort(key=lambda row: str(row.get("ts_code", "")))
        return
    if sort_by == "avg_amount":
        rows.sort(key=lambda row: (-float(row.get("avg_amount") or 0), str(row.get("ts_code", ""))))
        return
    raise ValueError(f"unsupported universe sort: {sort_by}")


def _exchange_from_ts_code(ts_code: str) -> str:
    if "." not in ts_code:
        return ""
    return ts_code.rsplit(".", 1)[1].upper()


def _is_st_name(name: str) -> bool:
    normalized = name.upper().replace("＊", "*").strip()
    return "ST" in normalized


def _read_rows(path: Path) -> List[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _average_amount(path: Path, as_of_date: date, window: int) -> Optional[float]:
    if window <= 0:
        raise ValueError("liquidity_window must be positive")
    if not path.exists():
        return None

    rows = []
    for row in _read_rows(path):
        trade_date = parse_date(row.get("trade_date") or row.get("date"))
        amount = row.get("amount")
        if trade_date is None or trade_date > as_of_date or amount in (None, ""):
            continue
        rows.append((trade_date, float(amount)))

    if not rows:
        return None
    rows.sort(key=lambda item: item[0])
    recent = rows[-window:]
    return sum(amount for _, amount in recent) / len(recent)


def _write_rows(path: Path, rows: List[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fieldnames(rows: List[dict[str, str]]) -> List[str]:
    names: List[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    return names


def parse_csv_set(value: Optional[str]) -> Optional[Set[str]]:
    if value is None or not value.strip():
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def parse_exchange_set(value: Optional[str]) -> Optional[Set[str]]:
    parsed = parse_csv_set(value)
    if parsed is None:
        return None
    return {item.upper() for item in parsed}
