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

    selected.sort(key=lambda row: str(row.get("ts_code", "")))
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
    return listed_days >= filters.min_listed_days


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
