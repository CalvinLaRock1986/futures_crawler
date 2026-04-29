from __future__ import annotations

import csv
import os
from typing import Any, Iterable

from .models import OutputConfig


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

