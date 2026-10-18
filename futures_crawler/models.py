from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


AuthNone = Literal["none"]


@dataclass(frozen=True)
class AuthConfig:
    type: AuthNone = "none"


@dataclass(frozen=True)
class HttpConfig:
    user_agent: str = "futures-crawler/0.1.0"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_seconds: float = 0.5
    # Minimal interval between requests across threads (best-effort).
    min_interval_seconds: float = 0.0


@dataclass(frozen=True)
class EndpointConfig:
    method: str
    url: str
    headers: dict[str, str]
    params_template: dict[str, Any]
    json_template: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class PaginationConfig:
    strategy: Literal["page", "cursor", "none"] = "page"
    start_page: int = 1

    page_param: str = "page"
    page_size_param: str = "page_size"
    page_size: int = 20

    records_path: str = "items"
    next_page_path: Optional[str] = None  # null means no more

    cursor_path: Optional[str] = None  # for request params
    next_cursor_path: Optional[str] = None
    done_when_cursor_missing: bool = True


@dataclass(frozen=True)
class ClosePriceConfig:
    enabled: bool = False
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    param_name: str = "hycode"
    trend_path: str = "data.trend"
    close_key: str = "close"


@dataclass(frozen=True)
class DetailConfig:
    enabled: bool = True
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    params_template: dict[str, Any] = field(default_factory=dict)
    # Map detail request param -> list record path, e.g. {"company": "company"}.
    params_from_list: dict[str, str] = field(default_factory=dict)

    # Backward compatible single-id mode (kept for existing configs).
    id_path_in_list: str = "id"
    detail_url_template: str = ""
    detail_records_path: str = ""


@dataclass(frozen=True)
class FieldMapping:
    name: str
    source: Literal["list", "detail"]
    path: str
    default: str = ""


@dataclass(frozen=True)
class OutputConfig:
    csv_path: str
    encoding: str = "utf-8"
    newline: str = ""
    # If True: only write combined report CSV (no main merged file).
    split_only: bool = False


@dataclass(frozen=True)
class JobConfig:
    contract: str
    variety: str = ""
    csv_path: str = ""


@dataclass(frozen=True)
class CrawlerConfig:
    auth: AuthConfig
    http: HttpConfig
    list_endpoint: EndpointConfig
    pagination: PaginationConfig
    detail: DetailConfig
    close_price: ClosePriceConfig = field(default_factory=ClosePriceConfig)
    fields: list[FieldMapping] = field(default_factory=list)
    output: OutputConfig = field(default_factory=lambda: OutputConfig(csv_path="output.csv"))
    jobs: list[JobConfig] = field(default_factory=list)

