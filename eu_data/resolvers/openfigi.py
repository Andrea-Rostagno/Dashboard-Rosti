"""
OpenFIGI resolver — maps ticker + exchange → ISIN (and other identifiers).

API: https://api.openfigi.com/v3/mapping
Free tier: 25 requests/minute without API key.
No registration required for basic use.
"""

from __future__ import annotations
import time
import logging

from eu_data.utils.http import RobustHTTPClient
from eu_data.utils.logger import get_logger

logger = get_logger(__name__)


class OpenFIGIResolver:
    """
    Resolve European ticker symbols to ISIN via the free OpenFIGI API.

    Converts: ticker + exchange code → ISIN + additional metadata.

    Exchange code mappings follow the OpenFIGI exchCode convention.
    """

    BASE_URL = "https://api.openfigi.com/v3/mapping"

    # OpenFIGI exchCode for each European market suffix
    EXCHANGE_CODES: dict[str, str] = {
        ".PA": "FP",    # Euronext Paris
        ".MI": "IM",    # Borsa Italiana
        ".DE": "GY",    # XETRA
        ".F":  "GF",    # Frankfurt
        ".MC": "SM",    # BME Madrid
        ".AS": "NA",    # Euronext Amsterdam
        ".L":  "LN",    # London Stock Exchange
        ".VX": "VX",    # SIX Swiss Exchange
        ".BR": "BB",    # Euronext Brussels
        ".LS": "PL",    # Euronext Lisbon
        ".ST": "SS",    # Nasdaq Stockholm
        ".CO": "DC",    # Nasdaq Copenhagen
        ".HE": "HF",    # Nasdaq Helsinki
        ".OL": "OS",    # Oslo Bors
        ".AT": "AV",    # Vienna (Austria)
        ".IR": "ID",    # Irish Stock Exchange
        ".WA": "PW",    # Warsaw Stock Exchange
        ".PR": "PX",    # Prague Stock Exchange
        ".BU": "BU",    # Budapest Stock Exchange
        ".ZA": "ZA",    # Johannesburg (for reference)
    }

    def __init__(
        self,
        api_key: str | None = None,
        http_client: RobustHTTPClient | None = None,
    ) -> None:
        """
        Parameters
        ----------
        api_key : optional OpenFIGI API key for higher rate limits.
        http_client : shared RobustHTTPClient instance.
        """
        self._api_key = api_key
        self._http = http_client or RobustHTTPClient()
        self._last_call: float = 0.0
        # Without API key: 25 req/min = ~2.4s interval
        self._min_interval: float = 2.5 if not api_key else 0.3

    def _rate_limit(self) -> None:
        now = time.monotonic()
        wait = self._min_interval - (now - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _ticker_base(self, ticker: str) -> str:
        """Strip exchange suffix to get bare ticker symbol."""
        ticker = ticker.upper().strip()
        for sfx in sorted(self.EXCHANGE_CODES.keys(), key=len, reverse=True):
            if ticker.endswith(sfx.upper()):
                return ticker[: -len(sfx)]
        return ticker

    def _exch_code(self, ticker: str) -> str | None:
        """Derive OpenFIGI exchCode from ticker suffix."""
        ticker = ticker.upper().strip()
        for sfx, code in sorted(
            self.EXCHANGE_CODES.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if ticker.endswith(sfx.upper()):
                return code
        return None

    def resolve(self, ticker: str) -> dict | None:
        """
        Resolve a ticker to ISIN and metadata via OpenFIGI.

        Parameters
        ----------
        ticker : e.g. "HO.PA", "ENI.MI", "BP.L"

        Returns
        -------
        dict with keys: isin, name, exchCode, marketSector, securityType, ticker
        or None if not found.
        """
        base = self._ticker_base(ticker)
        exch = self._exch_code(ticker)

        queries: list[dict] = []
        if exch:
            queries.append({"idType": "TICKER", "idValue": base, "exchCode": exch})
        # Also try without exchCode as fallback
        queries.append({"idType": "TICKER", "idValue": base})

        headers: dict = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-OPENFIGI-APIKEY"] = self._api_key

        for query_batch in [queries[:1], queries[1:]]:
            if not query_batch:
                continue
            self._rate_limit()
            try:
                resp = self._http.post(
                    self.BASE_URL,
                    json=query_batch,
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code == 429:
                    logger.warning("OpenFIGI rate limit hit — waiting 60s")
                    time.sleep(60)
                    continue
                data = resp.json()
            except Exception as exc:
                logger.warning("OpenFIGI request failed: %s", exc)
                continue

            _best_partial: dict | None = None
            for item in data:
                if "error" in item:
                    logger.debug("OpenFIGI error for %s: %s", ticker, item["error"])
                    continue
                for d in item.get("data", []):
                    # Validate raw isin field — OpenFIGI sometimes puts FIGI codes
                    # (e.g. "BBG000BCFRQ6") in the isin field; reject those.
                    raw_isin = d.get("isin", "")
                    if raw_isin and (
                        len(raw_isin) != 12
                        or raw_isin[:2] not in self._VALID_ISIN_PREFIXES
                    ):
                        raw_isin = None
                    isin = raw_isin or self._find_isin(d)
                    name = d.get("name", "")
                    if isin:
                        return {
                            "isin": isin,
                            "name": name,
                            "exchCode": d.get("exchCode", ""),
                            "marketSector": d.get("marketSector", ""),
                            "securityType": d.get("securityType", ""),
                            "ticker": d.get("ticker", base),
                            "figi": d.get("figi", ""),
                        }
                    # Capture partial result (name + figi) even without ISIN
                    if name and not _best_partial:
                        _best_partial = {
                            "isin": None,
                            "name": name,
                            "exchCode": d.get("exchCode", ""),
                            "marketSector": d.get("marketSector", ""),
                            "securityType": d.get("securityType", ""),
                            "ticker": d.get("ticker", base),
                            "figi": d.get("figi", ""),
                        }

            if _best_partial:
                logger.info("OpenFIGI: no ISIN for %s, returning partial (name=%s)",
                            ticker, _best_partial["name"])
                return _best_partial

        logger.warning("OpenFIGI: no result for ticker=%s", ticker)
        return None

    # Valid ISO-3166-1 alpha-2 country codes that can start an ISIN
    _VALID_ISIN_PREFIXES = frozenset([
        "AR","AT","AU","BE","BR","CA","CH","CN","CZ","DE","DK","ES","FI",
        "FR","GB","GR","HK","HU","IE","IN","IT","JP","KR","LU","MX","NL",
        "NO","NZ","PL","PT","RU","SE","SG","TH","TR","TW","US","ZA",
    ])

    def _find_isin(self, d: dict) -> str | None:
        """Some OpenFIGI responses embed ISIN inside shareClassFIGI or compositeFIGI.

        An ISIN must start with a valid ISO-3166-1 alpha-2 country code
        followed by 10 alphanumeric characters.  FIGI codes (BBG…) do NOT
        start with a country code and are filtered out here.
        """
        import re
        isin_re = re.compile(r"\b([A-Z]{2}[A-Z0-9]{10})\b")
        for v in d.values():
            if isinstance(v, str):
                for m in isin_re.finditer(v):
                    candidate = m.group(1)
                    if candidate[:2] in self._VALID_ISIN_PREFIXES:
                        return candidate
        return None

    def get_isin(self, ticker: str) -> str | None:
        """Shortcut: return only the ISIN for a ticker."""
        result = self.resolve(ticker)
        return result["isin"] if result else None
