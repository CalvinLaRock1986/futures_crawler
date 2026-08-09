from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Tuple

from .models import (
    AuthConfig,
    ClosePriceConfig,
    CrawlerConfig,
    DetailConfig,
    EndpointConfig,
    FieldMapping,
    HttpConfig,
    OutputConfig,
    PaginationConfig,
)


def _require_key(d: dict[str, Any], key: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing required config key: {key}")
    return d[key]


def load_config(path: str) -> CrawlerConfig:
    """
    Load config from YAML or JSON.

    Notes:
    - For YAML we require PyYAML (`yaml` package) to be installed.
    - For JSON, only the stdlib is needed.
    """
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    if ext == ".json":
        data = json.loads(raw)
    elif ext in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as e:
            # Fallback: parse the limited YAML subset used by this project's templates.
            data = _load_yaml_subset(raw)
        else:
            data = yaml.safe_load(raw)
    else:
        raise ValueError(f"Unsupported config extension: {ext}")

    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping/object.")

    auth_type = (_require_key(data, "auth") or {}).get("type", "none")
    auth = AuthConfig(type=auth_type)  # type: ignore[arg-type]

    http_data = data.get("http", {}) or {}
    http = HttpConfig(
        user_agent=http_data.get("user_agent", "futures-crawler/0.1.0"),
        timeout_seconds=float(http_data.get("timeout_seconds", 30.0)),
        max_retries=int(http_data.get("max_retries", 3)),
        backoff_seconds=float(http_data.get("backoff_seconds", 0.5)),
        min_interval_seconds=float(http_data.get("min_interval_seconds", 0.0)),
    )

    list_ep = _require_key(data, "list_endpoint")
    list_endpoint = EndpointConfig(
        method=list_ep["method"],
        url=list_ep["url"],
        headers=list_ep.get("headers", {}) or {},
        params_template=list_ep.get("params_template", {}) or {},
        json_template=list_ep.get("json_template"),
    )

    pagination = data.get("pagination", {}) or {}
    pagination_cfg = PaginationConfig(
        strategy=pagination.get("strategy", "page"),
        start_page=int(pagination.get("start_page", 1)),
        page_param=pagination.get("page_param", "page"),
        page_size_param=pagination.get("page_size_param", "page_size"),
        page_size=int(pagination.get("page_size", 20)),
        records_path=pagination.get("records_path", "items"),
        next_page_path=pagination.get("next_page_path"),
        cursor_path=pagination.get("cursor_path"),
        next_cursor_path=pagination.get("next_cursor_path"),
        done_when_cursor_missing=bool(pagination.get("done_when_cursor_missing", True)),
    )

    detail_data = data.get("detail", {}) or {}
    detail = DetailConfig(
        enabled=bool(detail_data.get("enabled", True)),
        method=detail_data.get("method", "GET"),
        url=detail_data.get("url", ""),
        headers=detail_data.get("headers", {}) or {},
        params_template=detail_data.get("params_template", {}) or {},
        params_from_list=detail_data.get("params_from_list", {}) or {},
        id_path_in_list=detail_data.get("id_path_in_list", "id"),
        detail_url_template=detail_data.get("detail_url_template", ""),
        detail_records_path=detail_data.get("detail_records_path", ""),
    )

    close_price_data = data.get("close_price", {}) or {}
    close_price = ClosePriceConfig(
        enabled=bool(close_price_data.get("enabled", False)),
        method=close_price_data.get("method", "GET"),
        url=close_price_data.get("url", ""),
        headers=close_price_data.get("headers", {}) or {},
        param_name=close_price_data.get("param_name", "hycode"),
        trend_path=close_price_data.get("trend_path", "data.trend"),
        close_key=close_price_data.get("close_key", "close"),
    )

    fields_raw = _require_key(data, "fields")
    if not isinstance(fields_raw, list):
        raise ValueError("`fields` must be a list.")
    fields: list[FieldMapping] = []
    for item in fields_raw:
        fields.append(
            FieldMapping(
                name=item["name"],
                source=item["source"],
                path=item["path"],
                default=item.get("default", ""),
            )
        )

    output_data = data.get("output", {}) or {}
    output = OutputConfig(
        csv_path=output_data.get("csv_path", "output.csv"),
        encoding=output_data.get("encoding", "utf-8"),
        newline=output_data.get("newline", ""),
        split_only=bool(output_data.get("split_only", False)),
    )

    return CrawlerConfig(
        auth=auth,
        http=http,
        list_endpoint=list_endpoint,
        pagination=pagination_cfg,
        detail=detail,
        close_price=close_price,
        fields=fields,
        output=output,
    )


def config_to_dict(cfg: CrawlerConfig) -> dict[str, Any]:
    # convenience for debug/dry-run
    return asdict(cfg)


def _strip_comment(line: str) -> str:
    # Very small YAML subset: treat '#' as comment start unless it's inside quotes.
    # Our config template doesn't contain '#' inside quoted strings.
    if "#" not in line:
        return line
    return line.split("#", 1)[0].rstrip()


def _parse_scalar(value: str) -> Any:
    v = value.strip()
    if v == "" or v.lower() in {"null", "~"}:
        return None
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    # int
    if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
        try:
            return int(v)
        except ValueError:
            pass
    # float (best-effort)
    try:
        if any(ch in v for ch in [".", "e", "E"]):
            return float(v)
    except ValueError:
        pass
    return v


def _indent_of(line: str) -> int:
    # Only spaces are expected in our templates.
    return len(line) - len(line.lstrip(" "))


def _load_yaml_subset(raw: str) -> Any:
    """
    Parse a minimal YAML subset:
    - Nested mappings via indentation
    - Lists via "- " items
    - Scalar values (string/int/float/bool/null)

    This is intentionally not a full YAML parser; it's designed for this project's `config.yaml`.
    """
    lines = []
    for ln in raw.splitlines():
        stripped = _strip_comment(ln)
        if stripped.strip() == "":
            continue
        lines.append(stripped.rstrip("\n"))

    def parse_block(i: int, indent: int) -> Tuple[Any, int]:
        if i >= len(lines):
            return {}, i
        # Determine block type at current position.
        cur_line = lines[i]
        cur_indent = _indent_of(cur_line)
        if cur_indent < indent:
            return {}, i
        if cur_line.strip().startswith("- "):
            return parse_list(i, indent)
        return parse_mapping(i, indent)

    def parse_list(i: int, indent: int) -> Tuple[list[Any], int]:
        arr: list[Any] = []
        while i < len(lines):
            line = lines[i]
            if _indent_of(line) < indent:
                break
            if _indent_of(line) != indent or not line.strip().startswith("- "):
                break
            item_text = line.strip()[2:].strip()
            i += 1
            if item_text == "":
                # Nested block item.
                item, i = parse_block(i, indent + 2)
                arr.append(item)
                continue

            # List item is inline.
            if ":" in item_text:
                # Parse mapping item: "- key: value" and subsequent keys at indent+2.
                d: dict[str, Any] = {}
                key, rest = item_text.split(":", 1)
                key = key.strip()
                rest = rest.strip()
                d[key] = _parse_scalar(rest) if rest != "" else None
                # Consume following key/value lines for this item.
                while i < len(lines) and _indent_of(lines[i]) >= indent + 2 and not (
                    _indent_of(lines[i]) == indent and lines[i].strip().startswith("- ")
                ):
                    if _indent_of(lines[i]) < indent + 2:
                        break
                    sub = lines[i].strip()
                    if sub.startswith("- "):
                        break
                    if ":" not in sub:
                        break
                    k, r = sub.split(":", 1)
                    k = k.strip()
                    r = r.strip()
                    if r != "":
                        d[k] = _parse_scalar(r)
                        i += 1
                    else:
                        # Nested value for key.
                        i += 1
                        child, i = parse_block(i, indent + 4)
                        d[k] = child
                arr.append(d)
            else:
                arr.append(_parse_scalar(item_text))
        return arr, i

    def parse_mapping(i: int, indent: int) -> Tuple[dict[str, Any], int]:
        obj: dict[str, Any] = {}
        while i < len(lines):
            line = lines[i]
            line_indent = _indent_of(line)
            if line_indent < indent:
                break
            if line_indent != indent:
                break

            text = line.strip()
            if text.startswith("- "):
                # Mismatched indentation (list where mapping expected).
                break

            if ":" not in text:
                raise ValueError(f"Invalid YAML line (expected key: value): {line}")
            key, rest = text.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            if rest != "":
                obj[key] = _parse_scalar(rest)
                i += 1
            else:
                # Nested block (indent+2).
                i += 1
                child, i = parse_block(i, indent + 2)
                obj[key] = child
        return obj, i

    data, idx = parse_block(0, 0)
    if idx < len(lines):
        # Best-effort: ignore trailing whitespace-only blocks.
        pass
    return data

