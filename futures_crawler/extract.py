from __future__ import annotations

import re
from typing import Any, Optional

from .models import FieldMapping


_INDEX_RE = re.compile(r"\[(?P<i>[0-9]+)\]")


def get_by_path(data: Any, path: str) -> Any:
    """
    Extract value from nested dict/list by a simple dotted path.

    Supported examples:
    - "id"
    - "data.title"
    - "items[0].title"
    - "data.items[1].meta.price"
    - "" (returns the original data)
    """
    if path is None:
        return None
    if path == "":
        return data

    cur = data
    # Allow leading/trailing dots and ignore empty segments.
    for seg in [s for s in path.split(".") if s]:
        # Parse something like: "items[0][1]" into key="items" and indexes=[0,1].
        if "[" in seg:
            key, _rest = seg.split("[", 1)
            indexes = [int(x.group("i")) for x in _INDEX_RE.finditer(seg)]
        else:
            key = seg
            indexes = []

        key = key or ""
        if key:
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]

        for idx in indexes:
            if not isinstance(cur, (list, tuple)):
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
    return cur


def extract_fields(
    *,
    list_record: dict[str, Any],
    detail_record: Optional[dict[str, Any]],
    fields: list[FieldMapping],
) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in fields:
        src = list_record if f.source == "list" else detail_record
        if src is None:
            value = None
        else:
            value = get_by_path(src, f.path)
        if value is None:
            out[f.name] = f.default
        elif isinstance(value, (dict, list)):
            out[f.name] = str(value)
        else:
            out[f.name] = str(value)
    return out

