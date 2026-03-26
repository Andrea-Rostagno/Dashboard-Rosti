"""
Robust HTTP client with retry, timeout, rotating User-Agents and rate limiting.
Every network call in eu_data must go through this client.
"""

from __future__ import annotations
import time
import random
import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from eu_data.utils.logger import get_logger

logger = get_logger(__name__)


class EUDataHTTPError(Exception):
    """Raised when an HTTP request fails after all retries."""


class RobustHTTPClient:
    """
    HTTP client with retry, timeout, rotating User-Agents and basic rate limiting.

    Usage::

        client = RobustHTTPClient()
        data = client.get_json("https://api.gleif.org/api/v1/lei-records", params={"filter[isin]": "FR0000131104"})
    """

    USER_AGENTS: list[str] = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.2 Safari/605.1.15"
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) "
            "Gecko/20100101 Firefox/124.0"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ),
    ]

    # Minimum seconds between requests to the same base host (politeness)
    _MIN_INTERVAL: float = 0.25

    def __init__(
        self,
        default_timeout: int = 15,
        default_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.default_timeout = default_timeout
        self.default_retries = default_retries
        self._last_request_time: dict[str, float] = {}

        # Build a session with automatic urllib3 retries on transient errors
        self._session = requests.Session()
        retry_cfg = Retry(
            total=default_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_cfg)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _random_ua(self) -> str:
        return random.choice(self.USER_AGENTS)

    def _rate_limit(self, url: str) -> None:
        """Sleep if needed to respect _MIN_INTERVAL between calls to the same host."""
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
        except Exception:
            host = url
        now = time.monotonic()
        last = self._last_request_time.get(host, 0.0)
        wait = self._MIN_INTERVAL - (now - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request_time[host] = time.monotonic()

    def _build_headers(self, extra: dict | None) -> dict:
        headers = {
            "User-Agent": self._random_ua(),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if extra:
            headers.update(extra)
        return headers

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: int | None = None,
        retries: int | None = None,
        stream: bool = False,
    ) -> requests.Response:
        """
        Perform a GET request with retry, UA rotation and rate limiting.

        Raises EUDataHTTPError if the final response is 4xx/5xx.
        """
        self._rate_limit(url)
        _timeout = timeout or self.default_timeout
        _headers = self._build_headers(headers)
        max_attempts = (retries or self.default_retries) + 1

        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=_headers,
                    timeout=_timeout,
                    stream=stream,
                )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    logger.warning("Rate-limited by %s — waiting %ds", url, wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    logger.warning(
                        "HTTP %d from %s (attempt %d/%d)",
                        resp.status_code, url, attempt, max_attempts,
                    )
                    if attempt < max_attempts:
                        time.sleep(2 ** attempt)
                        continue
                    raise EUDataHTTPError(
                        f"HTTP {resp.status_code} from {url}"
                    )
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "Request error on %s attempt %d: %s", url, attempt, exc
                )
                if attempt < max_attempts:
                    time.sleep(2 ** attempt)

        raise EUDataHTTPError(
            f"All {max_attempts} attempts failed for {url}: {last_exc}"
        )

    def post(
        self,
        url: str,
        json: Any = None,
        data: Any = None,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        """Perform a POST request."""
        self._rate_limit(url)
        _timeout = timeout or self.default_timeout
        _headers = self._build_headers(headers)
        _headers["Content-Type"] = "application/json"
        resp = self._session.post(
            url, json=json, data=data, headers=_headers, timeout=_timeout
        )
        return resp

    def get_json(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> dict | list:
        """GET and parse JSON body. Raises EUDataHTTPError on failure."""
        resp = self.get(url, params=params, headers=headers, timeout=timeout)
        try:
            return resp.json()
        except Exception as exc:
            raise EUDataHTTPError(
                f"Could not parse JSON from {url}: {exc}\nBody: {resp.text[:300]}"
            ) from exc

    def download_binary(
        self,
        url: str,
        headers: dict | None = None,
        timeout: int | None = None,
        max_bytes: int = 50 * 1024 * 1024,   # 50 MB safety cap
    ) -> bytes:
        """Download binary content (ZIP, XHTML, PDF). Returns raw bytes."""
        resp = self.get(
            url,
            headers=headers,
            timeout=timeout or 60,
            stream=True,
        )
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            total += len(chunk)
            if total > max_bytes:
                raise EUDataHTTPError(
                    f"Download from {url} exceeded {max_bytes} bytes safety cap"
                )
            chunks.append(chunk)
        return b"".join(chunks)
