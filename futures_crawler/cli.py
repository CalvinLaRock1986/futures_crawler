from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace
from datetime import date, datetime
from typing import Optional

from .config import load_config
from .crawler import CrawlerEngine
from .feishu_sender import send_file_to_chat
from .storage import split_futures_report_csv
from .models import (
    AuthConfig,
    CrawlerConfig,
    DetailConfig,
    EndpointConfig,
    FieldMapping,
    HttpConfig,
    OutputConfig,
    PaginationConfig,
)

from unittest.mock import patch


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _resolve_output_path(path: str, *, contract: str = "") -> str:
    current_date = datetime.now().strftime("%Y-%m-%d")
    resolved = path.replace("{当前日期}", current_date).replace("{current_date}", current_date)
    if contract:
        resolved = resolved.replace("{合约}", contract).replace("{contract}", contract)
    return resolved


def _is_cn_workday(d: date) -> bool:
    try:
        from chinese_calendar import is_workday  # type: ignore
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Missing dependency `chinese_calendar`. Install it with: "
            "/opt/anaconda3/envs/future/bin/pip install chinese-calendar"
        ) from e
    return bool(is_workday(d))


def _run_and_optional_push(args: argparse.Namespace) -> str:
    cfg = load_config(args.config)
    if args.output:
        # CrawlerConfig is immutable, so we create a new config with replaced OutputConfig.
        cfg = replace(cfg, output=replace(cfg.output, csv_path=args.output))
    contract = str(cfg.list_endpoint.params_template.get("contract", "") or "")
    cfg = replace(
        cfg,
        output=replace(cfg.output, csv_path=_resolve_output_path(cfg.output.csv_path, contract=contract)),
    )
    engine = CrawlerEngine(cfg)
    run_result = engine.run(max_pages=args.max_pages, max_records=args.max_records, workers=args.workers)
    log = logging.getLogger("futures_crawler")

    if cfg.output.split_only:
        out_path = run_result
        log.info("Wrote report CSV: %s", out_path)
        push_paths = [out_path]
        out_summary = out_path
    else:
        out_path = run_result
        report_path = split_futures_report_csv(
            out_path,
            encoding=cfg.output.encoding,
            newline=cfg.output.newline,
        )
        log.info("Wrote main CSV: %s report=%s", out_path, report_path)
        push_paths = [out_path, report_path]
        out_summary = out_path

    app_id = args.feishu_app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = args.feishu_app_secret or os.environ.get("FEISHU_APP_SECRET")
    chat_id = args.feishu_chat_id or os.environ.get("FEISHU_CHAT_ID")
    if app_id and app_secret and chat_id:
        for p in push_paths:
            send_file_to_chat(app_id=app_id, app_secret=app_secret, chat_id=chat_id, file_path=p)
    return out_summary


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="futures-crawler")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")

    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run crawler and write CSV.")
    run_p.add_argument("--config", required=True, help="Path to config.yaml or config.json")
    run_p.add_argument("--output", default=None, help="Override output csv path.")
    run_p.add_argument("--max-pages", type=int, default=None)
    run_p.add_argument("--max-records", type=int, default=None)
    run_p.add_argument("--workers", type=int, default=8)
    run_p.add_argument("--feishu-app-id", default=None, help="Feishu app_id (or env FEISHU_APP_ID)")
    run_p.add_argument("--feishu-app-secret", default=None, help="Feishu app_secret (or env FEISHU_APP_SECRET)")
    run_p.add_argument("--feishu-chat-id", default=None, help="Target Feishu chat_id (or env FEISHU_CHAT_ID)")

    run_workday_p = sub.add_parser("run-workday", help="Run only on China workdays.")
    run_workday_p.add_argument("--config", required=True, help="Path to config.yaml or config.json")
    run_workday_p.add_argument("--output", default=None, help="Override output csv path.")
    run_workday_p.add_argument("--max-pages", type=int, default=None)
    run_workday_p.add_argument("--max-records", type=int, default=None)
    run_workday_p.add_argument("--workers", type=int, default=8)
    run_workday_p.add_argument("--feishu-app-id", default=None, help="Feishu app_id (or env FEISHU_APP_ID)")
    run_workday_p.add_argument("--feishu-app-secret", default=None, help="Feishu app_secret (or env FEISHU_APP_SECRET)")
    run_workday_p.add_argument("--feishu-chat-id", default=None, help="Target Feishu chat_id (or env FEISHU_CHAT_ID)")

    validate_p = sub.add_parser("validate-config", help="Validate config and exit.")
    validate_p.add_argument("--config", required=True)

    mock_p = sub.add_parser("run-mock", help="Run with offline mocked API responses.")
    mock_p.add_argument("--output", required=True, help="Output CSV path for the mock run.")
    mock_p.add_argument("--workers", type=int, default=4)

    args = parser.parse_args(argv)
    _setup_logging(bool(args.verbose))

    if args.cmd == "validate-config":
        _ = load_config(args.config)
        print("OK")
        return

    if args.cmd == "run":
        print(_run_and_optional_push(args))
        return

    if args.cmd == "run-workday":
        today = date.today()
        if not _is_cn_workday(today):
            print(f"Skip: {today.isoformat()} is not a China workday.")
            return
        print(_run_and_optional_push(args))
        return

    if args.cmd == "run-mock":
        # A tiny end-to-end demo without real network calls.
        http_cfg = HttpConfig(user_agent="mock", timeout_seconds=5, max_retries=0, backoff_seconds=0)
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
        cfg = CrawlerConfig(
            auth=AuthConfig(type="none"),
            http=http_cfg,
            list_endpoint=list_ep,
            pagination=pagination,
            detail=detail,
            fields=fields,
            output=OutputConfig(csv_path=args.output, encoding="utf-8", newline=""),
        )

        def fake_request_json(*, method: str, url: str, params=None, headers=None, json_body=None, timeout_seconds=None):
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
            out_path = engine.run(workers=args.workers)
            print(out_path)
            return

    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    main(sys.argv[1:])

