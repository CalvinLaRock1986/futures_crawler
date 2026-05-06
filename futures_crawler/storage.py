from __future__ import annotations

import csv
import os
from typing import Any, Iterable

from .models import OutputConfig

# Split outputs for futures reports (Chinese column names).
LONG_SPLIT_FIELDS = [
    "交易日期",
    "合约",
    "品种",
    "会员简称",
    "多单持仓",
    "多单增减",
    "多单持仓均价",
]
SHORT_SPLIT_FIELDS = [
    "交易日期",
    "合约",
    "品种",
    "会员简称",
    "空单持仓",
    "空单增减",
    "空单持仓均价",
]


def _is_blank_or_zero(value: Any) -> bool:
    """True if missing, empty, non-numeric, or numeric zero (used as 'no position' on one side)."""
    if value is None:
        return True
    text = str(value).strip()
    if text == "":
        return True
    try:
        return float(text) == 0.0
    except ValueError:
        return True


def _to_number(value: Any) -> float:
    text = str(value).strip()
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def split_futures_report_csv(
    main_csv_path: str,
    *,
    encoding: str = "utf-8",
    newline: str = "",
) -> tuple[str, str]:
    """
    Split the main CSV into two files next to it:
    `{stem}_多单.csv` and `{stem}_空单.csv`.
    """
    base, ext = os.path.splitext(main_csv_path)
    long_path = f"{base}_多单{ext}"
    short_path = f"{base}_空单{ext}"
    parent = os.path.dirname(main_csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(main_csv_path, "r", encoding=encoding, newline=newline) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    def project(fields: list[str], row: dict[str, Any]) -> dict[str, str]:
        return {k: str(row.get(k, "") or "") for k in fields}

    long_rows = sorted(
        [r for r in rows if not _is_blank_or_zero(r.get("多单持仓"))],
        key=lambda r: _to_number(r.get("多单持仓", "")),
        reverse=True,
    )
    short_rows = sorted(
        [r for r in rows if not _is_blank_or_zero(r.get("空单持仓"))],
        key=lambda r: _to_number(r.get("空单持仓", "")),
        reverse=True,
    )

    with open(long_path, "w", encoding=encoding, newline=newline) as f:
        w = csv.DictWriter(f, fieldnames=LONG_SPLIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in long_rows:
            w.writerow(project(LONG_SPLIT_FIELDS, row))

    with open(short_path, "w", encoding=encoding, newline=newline) as f:
        w = csv.DictWriter(f, fieldnames=SHORT_SPLIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in short_rows:
            w.writerow(project(SHORT_SPLIT_FIELDS, row))

    return long_path, short_path


def write_futures_split_rows(
    *,
    output: OutputConfig,
    rows: Iterable[dict[str, str]],
) -> tuple[str, str]:
    """Write long/short CSVs directly from row dicts (same paths as split_futures_report_csv)."""
    base, ext = os.path.splitext(output.csv_path)
    long_path = f"{base}_多单{ext}"
    short_path = f"{base}_空单{ext}"
    parent = os.path.dirname(output.csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    rows_list = list(rows)

    def project(fields: list[str], row: dict[str, Any]) -> dict[str, str]:
        return {k: str(row.get(k, "") or "") for k in fields}

    long_rows = sorted(
        [r for r in rows_list if not _is_blank_or_zero(r.get("多单持仓"))],
        key=lambda r: _to_number(r.get("多单持仓", "")),
        reverse=True,
    )
    short_rows = sorted(
        [r for r in rows_list if not _is_blank_or_zero(r.get("空单持仓"))],
        key=lambda r: _to_number(r.get("空单持仓", "")),
        reverse=True,
    )

    with open(long_path, "w", encoding=output.encoding, newline=output.newline) as f:
        w = csv.DictWriter(f, fieldnames=LONG_SPLIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in long_rows:
            w.writerow(project(LONG_SPLIT_FIELDS, row))

    with open(short_path, "w", encoding=output.encoding, newline=output.newline) as f:
        w = csv.DictWriter(f, fieldnames=SHORT_SPLIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in short_rows:
            w.writerow(project(SHORT_SPLIT_FIELDS, row))

    return long_path, short_path


def write_csv_overwrite(
    *,
    output: OutputConfig,
    rows: Iterable[dict[str, str]],
    fieldnames: list[str],
) -> str:
    out_path = output.csv_path
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(out_path, "w", encoding=output.encoding, newline=output.newline) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path

