from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import threading
from typing import Any, Optional

from .models import HttpConfig


class HttpClient:
    def __init__(self, http_cfg: HttpConfig) -> None:
        self.http_cfg = http_cfg
        self._rate_lock = threading.Lock()
        self._last_request_ts: float = 0.0

    def _throttle(self) -> None:
        min_interval = float(getattr(self.http_cfg, "min_interval_seconds", 0.0) or 0.0)
        if min_interval <= 0:
            return
        with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts if self._last_request_ts else None
            if elapsed is None:
                self._last_request_ts = now
                return
            wait_s = min_interval - elapsed
            if wait_s > 0:
                time.sleep(wait_s)
                now = time.monotonic()
            self._last_request_ts = now

    def request_json(
        self,
        *,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        json_body: Optional[dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        timeout = float(timeout_seconds if timeout_seconds is not None else self.http_cfg.timeout_seconds)
        method_upper = method.upper()
        all_headers: dict[str, str] = {"User-Agent": self.http_cfg.user_agent}
        if headers:
            all_headers.update(headers)

        # Build URL query string for GET-like methods.
        request_url = url
        data_bytes: Optional[bytes] = None
        if params and method_upper in {"GET", "DELETE"}:
            request_url = self._with_query_params(url, params)
        elif params and method_upper not in {"GET", "DELETE"} and json_body is None:
            # Some APIs accept query params for POST as well.
            request_url = self._with_query_params(url, params)

        if json_body is not None:
            data_bytes = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            all_headers.setdefault("Content-Type", "application/json")

        max_attempts = max(1, self.http_cfg.max_retries + 1)
        backoff_base = max(0.0, float(self.http_cfg.backoff_seconds))

        last_err: Optional[BaseException] = None
        for attempt in range(max_attempts):
            try:
                self._throttle()
                req = urllib.request.Request(
                    request_url,
                    data=data_bytes if method_upper not in {"GET", "DELETE"} else None,
                    headers=all_headers,
                    method=method_upper,
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_err = e
                status = getattr(e, "code", None)
                should_retry = status in {429} or (status is not None and 500 <= int(status) <= 599)
                if not should_retry or attempt >= max_attempts - 1:
                    raise
                sleep_s = backoff_base * (2**attempt) + random.uniform(0, 0.2)
                time.sleep(sleep_s)
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
                if attempt >= max_attempts - 1:
                    raise
                sleep_s = backoff_base * (2**attempt) + random.uniform(0, 0.2)
                time.sleep(sleep_s)

        # Unreachable in normal flow (loop either returns or raises).
        raise RuntimeError(f"Request failed: {last_err!r}")

    @staticmethod
    def _with_query_params(url: str, params: dict[str, Any]) -> str:
        # urlencode keeps simple types; values are assumed to be scalar.
        query = urllib.parse.urlencode(params, doseq=True)
        joiner = "&" if "?" in url else "?"
        return f"{url}{joiner}{query}"

