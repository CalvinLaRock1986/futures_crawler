from __future__ import annotations

import concurrent.futures
import logging
from datetime import datetime
from typing import Any, Optional

from .config import config_to_dict
from .extract import extract_fields, get_by_path
from .http_client import HttpClient
from .models import CrawlerConfig
from .storage import write_csv_overwrite, write_futures_split_rows


logger = logging.getLogger("futures_crawler")


class CrawlerEngine:
    def __init__(self, cfg: CrawlerConfig) -> None:
        self.cfg = cfg
        self.http = HttpClient(cfg.http)

    def run(
        self,
        *,
        max_pages: Optional[int] = None,
        max_records: Optional[int] = None,
        workers: int = 8,
    ) -> str | tuple[str, str]:
        """
        Run full crawl for configured pagination.

        Returns the main CSV path, or (long_csv_path, short_csv_path) when output.split_only is True.
        """
        logger.info("Crawler start: %s", config_to_dict(self.cfg))
        page = int(self.cfg.pagination.start_page)
        pages_done = 0
        all_rows: list[dict[str, str]] = []

        while True:
            if self.cfg.pagination.strategy == "none":
                pages_done = 1
            else:
                if max_pages is not None and pages_done >= max_pages:
                    break

            list_json = self._fetch_list(page=page)
            records = get_by_path(list_json, self.cfg.pagination.records_path)
            if not isinstance(records, list):
                raise ValueError(f"records_path={self.cfg.pagination.records_path} is not a list.")

            logger.info("Fetched page=%s records=%s", page, len(records))
            if max_records is not None and len(all_rows) >= max_records:
                break

            # Fetch details concurrently for each record.
            detail_jsons: list[Optional[dict[str, Any]]] = [None] * len(records)
            if self.cfg.detail.enabled:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
                    futures = {}
                    for i, rec in enumerate(records):
                        futures[ex.submit(self._fetch_detail, rec)] = i
                    for fut in concurrent.futures.as_completed(futures):
                        idx = futures[fut]
                        detail_jsons[idx] = fut.result()

            # Extract rows.
            for rec, det in zip(records, detail_jsons if self.cfg.detail.enabled else [None] * len(records)):
                if max_records is not None and len(all_rows) >= max_records:
                    break
                all_rows.append(extract_fields(list_record=rec, detail_record=det, fields=self.cfg.fields))

            pages_done += 1

            if max_records is not None and len(all_rows) >= max_records:
                break

            if self.cfg.pagination.strategy == "none":
                break

            if self.cfg.pagination.strategy == "page":
                if not self.cfg.pagination.next_page_path:
                    # Only one page unless explicit next_page_path is configured.
                    break
                next_page = get_by_path(list_json, self.cfg.pagination.next_page_path)
                if next_page is None:
                    break
                page = int(next_page)
            elif self.cfg.pagination.strategy == "cursor":
                if not self.cfg.pagination.next_cursor_path:
                    break
                next_cursor = get_by_path(list_json, self.cfg.pagination.next_cursor_path)
                if next_cursor is None:
                    break
                if not self.cfg.pagination.cursor_path:
                    break
                # Cursor is supplied via query params
                page_params = dict(self.cfg.list_endpoint.params_template)
                page_params[self.cfg.pagination.cursor_path] = next_cursor
                # We re-store it as part of params_template just for next request.
                # (Simpler than building a separate cursor param object.)
                self.cfg = self.cfg  # no-op; config is frozen dataclasses. We won't mutate it.
                # Fallback: rely on params_template already being cursor-less.
                # In practice, you should specify `params_template` for the initial cursor value if needed.
                raise NotImplementedError("cursor pagination requires additional cursor param wiring.")
            else:
                raise ValueError(f"Unsupported pagination strategy: {self.cfg.pagination.strategy}")

        fieldnames = [f.name for f in self.cfg.fields]
        if self.cfg.output.split_only:
            return write_futures_split_rows(output=self.cfg.output, rows=all_rows)
        return write_csv_overwrite(
            output=self.cfg.output,
            rows=all_rows,
            fieldnames=fieldnames,
        )

    def _fetch_list(self, *, page: int) -> dict[str, Any]:
        params = dict(self.cfg.list_endpoint.params_template)
        if self.cfg.pagination.strategy == "none":
            # No pagination: use params_template as-is.
            return self.http.request_json(
                method=self.cfg.list_endpoint.method,
                url=self.cfg.list_endpoint.url,
                params=params if params else None,
                headers=self.cfg.list_endpoint.headers,
            )
        if self.cfg.pagination.strategy == "page":
            params[self.cfg.pagination.page_param] = page
            params[self.cfg.pagination.page_size_param] = self.cfg.pagination.page_size
        elif self.cfg.pagination.strategy == "cursor":
            raise NotImplementedError("cursor pagination not fully wired yet.")
        else:
            raise ValueError(f"Unsupported pagination strategy: {self.cfg.pagination.strategy}")

        return self.http.request_json(
            method=self.cfg.list_endpoint.method,
            url=self.cfg.list_endpoint.url,
            params=params,
            headers=self.cfg.list_endpoint.headers,
        )

    def _fetch_detail(self, list_record: dict[str, Any]) -> Optional[dict[str, Any]]:
        detail = self.cfg.detail
        detail_url = detail.url
        detail_method = detail.method
        detail_params: Optional[dict[str, Any]] = None

        # New multi-parameter mode: request params are built from each list row.
        if detail.url:
            detail_params = dict(detail.params_template)
            for param_name, list_path in detail.params_from_list.items():
                detail_params[param_name] = get_by_path(list_record, list_path)
            detail_headers = dict(self.cfg.list_endpoint.headers)
            detail_headers.update(detail.headers)
        else:
            # Backward compatible single-id mode.
            rec_id = get_by_path(list_record, detail.id_path_in_list)
            if rec_id is None:
                return None
            detail_url = detail.detail_url_template.format(**{detail.id_path_in_list: rec_id, "id": rec_id})
            detail_method = "GET"
            detail_headers = self.cfg.list_endpoint.headers
            detail_params = None

        if not detail_url:
            return None

        detail_json = self.http.request_json(
            method=detail_method,
            url=detail_url,
            params=detail_params,
            headers=detail_headers,
        )
        if not detail.detail_records_path:
            if isinstance(detail_json, dict):
                return self._inject_latest_entries(detail_json)
            return None
        trimmed = get_by_path(detail_json, detail.detail_records_path)
        if isinstance(trimmed, dict):
            return self._inject_latest_entries(trimmed)
        return None

    def _inject_latest_entries(self, detail_data: dict[str, Any]) -> dict[str, Any]:
        """
        Compute latest-by-tradeDate objects for commonly used arrays in detail payload.
        """
        out = dict(detail_data)
        latest_company = self._latest_item_by_trade_date(out.get("companyPositionList"))
        latest_position_avg = self._latest_item_by_trade_date(out.get("positionAvgPriceList"))

        out["latestCompanyPosition"] = latest_company or {}
        out["latestPositionAvgPrice"] = latest_position_avg or {}
        out["latestCompanyPositionTradeDate"] = (latest_company or {}).get("tradeDate", "")
        out["latestPositionAvgPriceTradeDate"] = (latest_position_avg or {}).get("tradeDate", "")
        return out

    @staticmethod
    def _latest_item_by_trade_date(items: Any) -> Optional[dict[str, Any]]:
        if not isinstance(items, list) or not items:
            return None

        def key_fn(item: Any) -> tuple[int, datetime]:
            if not isinstance(item, dict):
                return (0, datetime.min)
            raw = item.get("tradeDate")
            if not isinstance(raw, str):
                return (0, datetime.min)
            try:
                return (1, datetime.strptime(raw, "%Y-%m-%d"))
            except ValueError:
                return (0, datetime.min)

        valid = [x for x in items if isinstance(x, dict)]
        if not valid:
            return None
        return max(valid, key=key_fn)

