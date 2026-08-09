from __future__ import annotations

import csv
import os
from typing import Any, Iterable

from .models import OutputConfig

# Split outputs for futures reports (Chinese column names).
LONG_SPLIT_FIELDS = [
    "名次",
    "会员简称",
    "多单持仓",
    "单量占比",
    "多单增减",
    "多单持仓均价",
    "收盘价",
    "持仓金额",
    "多单资金",
]
SHORT_SPLIT_FIELDS = [
    "名次",
    "会员简称",
    "空单持仓",
    "单量占比",
    "空单增减",
    "空单持仓均价",
    "收盘价",
    "持仓金额",
    "空单资金",
]

SPLIT_ROW_LIMIT = 20
COMBINED_SHORT_START_LINE = 28
TOTAL_LABEL = "合计"
SHARE_COLUMN = "单量占比"
AMOUNT_COLUMN = "持仓金额"
LONG_AMOUNT_SHARE_COLUMN = "多单资金"
SHORT_AMOUNT_SHARE_COLUMN = "空单资金"
LONG_POSITION_COLUMN = "多单持仓"
SHORT_POSITION_COLUMN = "空单持仓"
LONG_AVG_COLUMN = "多单持仓均价"
SHORT_AVG_COLUMN = "空单持仓均价"
CLOSE_PRICE_COLUMN = "收盘价"
LONG_AVG_TOTAL_LABEL = "看多均价"
SHORT_AVG_TOTAL_LABEL = "看空均价"
LONG_WEIGHTED_AVG_LABEL = "持多均价"
SHORT_WEIGHTED_AVG_LABEL = "持空均价"
LONG_SUM_COLUMNS = ("多单持仓", "多单增减")
SHORT_SUM_COLUMNS = ("空单持仓", "空单增减")


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


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)


def _sum_column(rows: list[dict[str, Any]], column: str) -> str:
    total = sum(_to_number(row.get(column, "")) for row in rows)
    return _format_number(total)


def _avg_column(rows: list[dict[str, Any]], column: str) -> str:
    if not rows:
        return ""
    avg = sum(_to_number(row.get(column, "")) for row in rows) / len(rows)
    return f"{avg:.2f}"


def _format_share_pct(position: float, total: float) -> str:
    if total <= 0:
        return ""
    return f"{position / total * 100:.2f}%"


def _calc_position_amount(row: dict[str, Any], *, position_column: str, avg_column: str) -> float:
    return _to_number(row.get(position_column, "")) * _to_number(row.get(avg_column, ""))


def _format_amount(value: float) -> str:
    return f"{value:.2f}"


def _sum_position_amount(
    rows: list[dict[str, Any]],
    *,
    position_column: str,
    avg_column: str,
) -> float:
    return sum(_calc_position_amount(r, position_column=position_column, avg_column=avg_column) for r in rows)


def _build_total_row(
    fields: list[str],
    data_rows: list[dict[str, Any]],
    *,
    sum_columns: tuple[str, ...],
    position_column: str,
    avg_column: str,
    avg_label: str,
    amount_share_column: str,
    total_amount: float,
) -> dict[str, str]:
    row = {field: "" for field in fields}
    row[fields[0]] = TOTAL_LABEL
    for column in sum_columns:
        if column in row:
            row[column] = _sum_column(data_rows, column)
    if SHARE_COLUMN in row:
        row[SHARE_COLUMN] = "100.00%"
    if avg_column in row:
        row[avg_column] = avg_label
    if CLOSE_PRICE_COLUMN in row:
        row[CLOSE_PRICE_COLUMN] = _avg_column(data_rows, avg_column)
    if AMOUNT_COLUMN in row:
        row[AMOUNT_COLUMN] = _format_amount(total_amount)
    if amount_share_column in row:
        row[amount_share_column] = "100.00%"
    return row


def _build_weighted_avg_row(
    fields: list[str],
    *,
    avg_column: str,
    weighted_avg_label: str,
    total_amount: float,
    total_position: float,
) -> dict[str, str]:
    row = {field: "" for field in fields}
    if avg_column in row:
        row[avg_column] = weighted_avg_label
    if CLOSE_PRICE_COLUMN in row:
        if total_position > 0:
            row[CLOSE_PRICE_COLUMN] = f"{total_amount / total_position:.2f}"
        else:
            row[CLOSE_PRICE_COLUMN] = ""
    return row


def _project_ranked(
    fields: list[str],
    row: dict[str, Any],
    rank: int,
    *,
    position_column: str,
    avg_column: str,
    amount_share_column: str,
    total_position: float,
    total_amount: float,
) -> dict[str, str]:
    amount = _calc_position_amount(row, position_column=position_column, avg_column=avg_column)
    out: dict[str, str] = {}
    for k in fields:
        if k == "名次":
            out[k] = str(rank)
        elif k == SHARE_COLUMN:
            out[k] = _format_share_pct(_to_number(row.get(position_column, "")), total_position)
        elif k == AMOUNT_COLUMN:
            out[k] = _format_amount(amount)
        elif k == amount_share_column:
            out[k] = _format_share_pct(amount, total_amount)
        else:
            out[k] = str(row.get(k, "") or "")
    return out


def _build_split_section_rows(
    fields: list[str],
    rows: list[dict[str, Any]],
    *,
    sum_columns: tuple[str, ...],
    position_column: str,
    avg_column: str,
    avg_label: str,
    weighted_avg_label: str,
    amount_share_column: str,
) -> list[dict[str, str]]:
    top_rows = rows[:SPLIT_ROW_LIMIT]
    total_position = sum(_to_number(row.get(position_column, "")) for row in top_rows)
    total_amount = _sum_position_amount(top_rows, position_column=position_column, avg_column=avg_column)
    section_rows: list[dict[str, str]] = []
    for rank, row in enumerate(top_rows, start=1):
        section_rows.append(
            _project_ranked(
                fields,
                row,
                rank,
                position_column=position_column,
                avg_column=avg_column,
                amount_share_column=amount_share_column,
                total_position=total_position,
                total_amount=total_amount,
            )
        )
    if top_rows:
        section_rows.append(
            _build_total_row(
                fields,
                top_rows,
                sum_columns=sum_columns,
                position_column=position_column,
                avg_column=avg_column,
                avg_label=avg_label,
                amount_share_column=amount_share_column,
                total_amount=total_amount,
            )
        )
        section_rows.append(
            _build_weighted_avg_row(
                fields,
                avg_column=avg_column,
                weighted_avg_label=weighted_avg_label,
                total_amount=total_amount,
                total_position=total_position,
            )
        )
    return section_rows


def _write_split_file(
    path: str,
    *,
    fields: list[str],
    rows: list[dict[str, Any]],
    sum_columns: tuple[str, ...],
    position_column: str,
    avg_column: str,
    avg_label: str,
    weighted_avg_label: str,
    amount_share_column: str,
    encoding: str,
    newline: str,
) -> None:
    section_rows = _build_split_section_rows(
        fields,
        rows,
        sum_columns=sum_columns,
        position_column=position_column,
        avg_column=avg_column,
        avg_label=avg_label,
        weighted_avg_label=weighted_avg_label,
        amount_share_column=amount_share_column,
    )
    with open(path, "w", encoding=encoding, newline=newline) as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in section_rows:
            writer.writerow(row)


def _write_combined_long_csv(
    path: str,
    *,
    long_rows: list[dict[str, Any]],
    short_rows: list[dict[str, Any]],
    encoding: str,
    newline: str,
) -> None:
    long_section = _build_split_section_rows(
        LONG_SPLIT_FIELDS,
        long_rows,
        sum_columns=LONG_SUM_COLUMNS,
        position_column=LONG_POSITION_COLUMN,
        avg_column=LONG_AVG_COLUMN,
        avg_label=LONG_AVG_TOTAL_LABEL,
        weighted_avg_label=LONG_WEIGHTED_AVG_LABEL,
        amount_share_column=LONG_AMOUNT_SHARE_COLUMN,
    )
    short_section = _build_split_section_rows(
        SHORT_SPLIT_FIELDS,
        short_rows,
        sum_columns=SHORT_SUM_COLUMNS,
        position_column=SHORT_POSITION_COLUMN,
        avg_column=SHORT_AVG_COLUMN,
        avg_label=SHORT_AVG_TOTAL_LABEL,
        weighted_avg_label=SHORT_WEIGHTED_AVG_LABEL,
        amount_share_column=SHORT_AMOUNT_SHARE_COLUMN,
    )
    blank_rows_needed = COMBINED_SHORT_START_LINE - 2 - len(long_section)
    if blank_rows_needed < 0:
        raise ValueError(
            f"Long section has {len(long_section)} rows; cannot start short section at line "
            f"{COMBINED_SHORT_START_LINE}."
        )

    with open(path, "w", encoding=encoding, newline=newline) as f:
        writer = csv.writer(f)
        writer.writerow(LONG_SPLIT_FIELDS)
        for row in long_section:
            writer.writerow([row.get(field, "") for field in LONG_SPLIT_FIELDS])
        for _ in range(blank_rows_needed):
            writer.writerow([])
        writer.writerow(SHORT_SPLIT_FIELDS)
        for row in short_section:
            writer.writerow([row.get(field, "") for field in SHORT_SPLIT_FIELDS])


def read_combined_report_sections(
    path: str,
    *,
    encoding: str = "utf-8",
    newline: str = "",
) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    """Parse combined report CSV into long and short sections."""
    with open(path, "r", encoding=encoding, newline=newline) as f:
        all_rows = list(csv.reader(f))

    long_header = all_rows[0]
    long_data: list[dict[str, str]] = []
    idx = 1
    while idx < len(all_rows) and any(all_rows[idx]):
        long_data.append(dict(zip(long_header, all_rows[idx])))
        idx += 1

    while idx < len(all_rows) and not any(all_rows[idx]):
        idx += 1

    short_start_line = idx + 1
    short_header = all_rows[idx]
    idx += 1
    short_data: list[dict[str, str]] = []
    while idx < len(all_rows) and any(all_rows[idx]):
        short_data.append(dict(zip(short_header, all_rows[idx])))
        idx += 1

    return long_data, short_data, short_start_line


def split_futures_report_csv(
    main_csv_path: str,
    *,
    encoding: str = "utf-8",
    newline: str = "",
) -> str:
    """Build combined long+short report CSV next to the main CSV path."""
    base, ext = os.path.splitext(main_csv_path)
    out_path = f"{base}_report{ext}"
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(main_csv_path, "r", encoding=encoding, newline=newline) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

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

    _write_combined_long_csv(
        out_path,
        long_rows=long_rows,
        short_rows=short_rows,
        encoding=encoding,
        newline=newline,
    )

    return out_path


def write_futures_split_rows(
    *,
    output: OutputConfig,
    rows: Iterable[dict[str, str]],
) -> str:
    """Write combined long+short report CSV to `output.csv_path`."""
    out_path = output.csv_path
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    rows_list = list(rows)

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

    _write_combined_long_csv(
        out_path,
        long_rows=long_rows,
        short_rows=short_rows,
        encoding=output.encoding,
        newline=output.newline,
    )

    return out_path


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

