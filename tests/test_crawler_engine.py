from __future__ import annotations

import csv
import os
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from futures_crawler.crawler import CrawlerEngine
from futures_crawler.models import (
    CrawlerConfig,
    DetailConfig,
    EndpointConfig,
    FieldMapping,
    HttpConfig,
    AuthConfig,
    OutputConfig,
    PaginationConfig,
)


class CrawlerEngineTests(unittest.TestCase):
    def _make_cfg(self, csv_path: str) -> CrawlerConfig:
        http_cfg = HttpConfig(user_agent="test", timeout_seconds=5, max_retries=0, backoff_seconds=0)
        list_ep = EndpointConfig(
            method="GET",
            url="https://example.test/api/items",
            headers={},
            params_template={},
            json_template=None,
        )
        pagination = PaginationConfig(
            strategy="page",
            start_page=1,
            page_param="page",
            page_size_param="page_size",
            page_size=2,
            records_path="data.items",
            next_page_path="data.next_page",
        )
        detail = DetailConfig(
            enabled=True,
            method="GET",
            url="https://example.test/api/item_detail",
            params_template={},
            params_from_list={"id": "id"},
            detail_records_path="",
        )
        fields = [
            FieldMapping(name="id", source="list", path="id", default=""),
            FieldMapping(name="title", source="detail", path="data.title", default=""),
        ]
        output = OutputConfig(csv_path=csv_path, encoding="utf-8", newline="")
        return CrawlerConfig(
            auth=AuthConfig(type="none"),
            http=http_cfg,
            list_endpoint=list_ep,
            pagination=pagination,
            detail=detail,
            fields=fields,
            output=output,
        )

    def test_pagination_and_detail_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_csv = os.path.join(td, "out.csv")
            cfg = self._make_cfg(out_csv)

            def fake_request_json(*, method: str, url: str, params: Any = None, headers: Any = None, json_body: Any = None, timeout_seconds: Any = None) -> Any:
                if url.endswith("/api/items") and method.upper() == "GET":
                    page = int(params.get("page"))
                    if page == 1:
                        return {"data": {"items": [{"id": 1}, {"id": 2}], "next_page": 2}}
                    if page == 2:
                        return {"data": {"items": [{"id": 3}], "next_page": None}}
                if url.endswith("/api/item_detail") and method.upper() == "GET":
                    rec_id = int(params["id"])
                    return {"data": {"title": f"t{rec_id}"}}
                raise AssertionError(f"Unexpected request: {method} {url} {params}")

            with patch("futures_crawler.crawler.HttpClient") as http_cls:
                http_instance = http_cls.return_value
                http_instance.request_json.side_effect = fake_request_json

                engine = CrawlerEngine(cfg)
                engine.run(workers=3)

            with open(out_csv, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

            got_ids = [int(r["id"]) for r in rows]
            self.assertEqual(got_ids, [1, 2, 3])
            self.assertEqual([r["title"] for r in rows], ["t1", "t2", "t3"])

    def test_missing_detail_field_uses_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_csv = os.path.join(td, "out.csv")
            cfg = self._make_cfg(out_csv)

            def fake_request_json(*, method: str, url: str, params: Any = None, headers: Any = None, json_body: Any = None, timeout_seconds: Any = None) -> Any:
                if url.endswith("/api/items"):
                    return {"data": {"items": [{"id": 1}], "next_page": None}}
                if url.endswith("/api/item_detail"):
                    return {"data": {}}  # no title
                raise AssertionError("Unexpected call")

            with patch("futures_crawler.crawler.HttpClient") as http_cls:
                http_instance = http_cls.return_value
                http_instance.request_json.side_effect = fake_request_json

                engine = CrawlerEngine(cfg)
                engine.run(workers=2)

            with open(out_csv, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(rows[0]["id"], "1")
            self.assertEqual(rows[0]["title"], "")


if __name__ == "__main__":
    unittest.main()

