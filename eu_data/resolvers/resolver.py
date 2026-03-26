"""
EntityResolver — high-level company identity resolution pipeline.

Chains: ticker → OpenFIGI → ISIN → GLEIF → LEI + metadata
Also supports: ISIN-only or name-only resolution paths.
"""

from __future__ import annotations
import logging

from eu_data.models.company import CompanyIdentity
from eu_data.resolvers.openfigi import OpenFIGIResolver
from eu_data.resolvers.gleif import GLEIFResolver
from eu_data.utils.http import RobustHTTPClient
from eu_data.utils.logger import get_logger

logger = get_logger(__name__)


# Country code from exchange suffix
_SUFFIX_TO_COUNTRY: dict[str, str] = {
    ".PA": "FR",
    ".MI": "IT",
    ".DE": "DE",
    ".F":  "DE",
    ".MC": "ES",
    ".AS": "NL",
    ".L":  "GB",
    ".VX": "CH",
    ".BR": "BE",
    ".LS": "PT",
    ".ST": "SE",
    ".CO": "DK",
    ".HE": "FI",
    ".OL": "NO",
    ".AT": "AT",
    ".IR": "IE",
    ".WA": "PL",
    ".PR": "CZ",
    ".BU": "HU",
}

# Default reporting currency per country
_COUNTRY_CURRENCY: dict[str, str] = {
    "FR": "EUR", "IT": "EUR", "DE": "EUR", "ES": "EUR",
    "NL": "EUR", "BE": "EUR", "PT": "EUR", "FI": "EUR",
    "AT": "EUR", "IE": "EUR",
    "GB": "GBP",
    "CH": "CHF",
    "SE": "SEK",
    "DK": "DKK",
    "NO": "NOK",
    "PL": "PLN",
    "CZ": "CZK",
    "HU": "HUF",
}

# Exchange display name per suffix
_SUFFIX_TO_EXCHANGE: dict[str, str] = {
    ".PA": "Euronext Paris",
    ".MI": "Borsa Italiana",
    ".DE": "XETRA",
    ".F":  "Frankfurt",
    ".MC": "BME Madrid",
    ".AS": "Euronext Amsterdam",
    ".L":  "London Stock Exchange",
    ".VX": "SIX Swiss Exchange",
    ".BR": "Euronext Brussels",
    ".LS": "Euronext Lisbon",
    ".ST": "Nasdaq Stockholm",
    ".CO": "Nasdaq Copenhagen",
    ".HE": "Nasdaq Helsinki",
    ".OL": "Oslo Bors",
}


class EntityResolver:
    """
    Resolve a ticker / ISIN / company name into a fully populated CompanyIdentity.

    Resolution chain:
    1. Detect exchange country from ticker suffix.
    2. Call OpenFIGI to map ticker → ISIN.
    3. Call GLEIF to map ISIN → LEI + legal name + country.
    4. Fallback: GLEIF name search if OpenFIGI fails.
    """

    def __init__(
        self,
        http_client: RobustHTTPClient | None = None,
        openfigi_api_key: str | None = None,
    ) -> None:
        self._http = http_client or RobustHTTPClient()
        self._openfigi = OpenFIGIResolver(
            api_key=openfigi_api_key, http_client=self._http
        )
        self._gleif = GLEIFResolver(http_client=self._http)

    def resolve(
        self,
        ticker: str | None = None,
        isin: str | None = None,
        company_name: str | None = None,
        country: str | None = None,
    ) -> CompanyIdentity:
        """
        Resolve company identity using available identifiers.

        At least one of ticker, isin, or company_name must be provided.

        Returns
        -------
        CompanyIdentity (always — may have low confidence if resolution fails)
        """
        if not any([ticker, isin, company_name]):
            raise ValueError("At least one of ticker, isin, company_name must be provided")

        # --- Step 0: detect country / currency from ticker suffix ---
        detected_country = country
        detected_exchange = None
        detected_currency = None

        if ticker:
            t_upper = ticker.upper().strip()
            for sfx in sorted(_SUFFIX_TO_COUNTRY.keys(), key=len, reverse=True):
                if t_upper.endswith(sfx.upper()):
                    if not detected_country:
                        detected_country = _SUFFIX_TO_COUNTRY[sfx]
                    detected_exchange = _SUFFIX_TO_EXCHANGE.get(sfx, sfx)
                    detected_currency = _COUNTRY_CURRENCY.get(
                        _SUFFIX_TO_COUNTRY[sfx], "EUR"
                    )
                    break

        currency = detected_currency or _COUNTRY_CURRENCY.get(
            detected_country or "", "EUR"
        )
        identity = CompanyIdentity(
            ticker=ticker,
            isin=isin,
            company_name=company_name or ticker,
            country=detected_country,
            exchange=detected_exchange,
            currency=currency,
            confidence=0.1,
            resolution_source="initial",
        )

        # --- Step 1: OpenFIGI ticker → ISIN ---
        _openfigi_name: str | None = None  # capture name even when ISIN not available
        if ticker and not isin:
            logger.info("OpenFIGI: resolving ticker %s", ticker)
            figi_result = self._openfigi.resolve(ticker)
            if figi_result:
                _openfigi_name = figi_result.get("name") or None
                if figi_result.get("isin"):
                    isin = figi_result["isin"]
                    identity.isin = isin
                    identity.confidence = 0.5
                    identity.resolution_source = "OpenFIGI"
                    if not identity.company_name or identity.company_name == ticker:
                        identity.company_name = _openfigi_name or ticker
                    logger.info("OpenFIGI resolved %s -> ISIN=%s", ticker, isin)
                else:
                    # OpenFIGI returned a match but no ISIN (e.g. only FIGI)
                    # Still capture the company name for GLEIF name search
                    if _openfigi_name and (not identity.company_name or identity.company_name == ticker):
                        identity.company_name = _openfigi_name
                    logger.info("OpenFIGI: no ISIN for %s, name=%s", ticker, _openfigi_name)
            else:
                logger.warning("OpenFIGI could not resolve %s", ticker)

        # --- Step 2: GLEIF ISIN → LEI + metadata ---
        if isin and not identity.lei:
            logger.info("GLEIF: resolving ISIN %s", isin)
            lei = self._gleif.get_lei_from_isin(isin)
            if lei:
                identity.lei = lei
                identity.confidence = 0.7
                identity.resolution_source = "GLEIF"
                # Fetch detailed entity info
                info = self._gleif.get_company_info(lei)
                if info:
                    if info.get("legal_name"):
                        identity.company_name = info["legal_name"]
                    if info.get("country") and not identity.country:
                        identity.country = info["country"]
                    identity.confidence = 0.9
                    identity.extra_metadata.update(info)
                    logger.info(
                        "GLEIF: ISIN %s → LEI %s | %s (%s)",
                        isin, lei, identity.company_name, identity.country,
                    )
            else:
                logger.warning("GLEIF: no LEI for ISIN %s", isin)

        # --- Step 3: GLEIF name search fallback ---
        if not identity.lei and (company_name or ticker):
            # Prefer: explicit company_name > OpenFIGI name > ticker base (without suffix)
            _base_name = (
                company_name
                or (_openfigi_name if _openfigi_name and _openfigi_name != ticker else None)
                or identity.company_name
                or (ticker or "").split(".")[0]
            )
            # Use OpenFIGI name if it's not just the raw ticker
            search_name = _base_name if (_base_name and _base_name != ticker) else (ticker or "").split(".")[0]

            logger.info("GLEIF name search fallback: %r (country=%s)", search_name, detected_country)

            # Build search variants: full name + stripped (remove legal suffix)
            _legal_suffixes = (" SA", " SAS", " NV", " AG", " PLC", " SE", " AB",
                               " ASA", " OY", " BV", " GmbH", " S.A.", " S.p.A.",
                               " S.A", " SPA", " SpA", " N.V.", " A.G.", " ASA")
            _search_variants = [search_name]
            _upper = search_name.upper()
            for sfx in _legal_suffixes:
                if _upper.endswith(sfx.upper()):
                    _search_variants.append(search_name[:len(search_name) - len(sfx)].strip())
                    break

            all_matches: list[dict] = []
            seen_leis: set = set()
            for sv in _search_variants:
                for m in self._gleif.search_by_name(sv, country=detected_country):
                    if m.get("lei") not in seen_leis:
                        seen_leis.add(m.get("lei"))
                        all_matches.append(m)

            if all_matches:
                # Rank candidates: prefer those with verified ESEF filings
                best = self._pick_best_gleif_match_with_esef(
                    all_matches, search_name, self._http
                )
                identity.lei = best["lei"]
                identity.company_name = best.get("legal_name") or identity.company_name
                if not identity.country and best.get("country"):
                    identity.country = best["country"]
                identity.confidence = 0.7 if best.get("has_esef") else 0.5
                identity.resolution_source = "GLEIF_name_search"
                logger.info(
                    "GLEIF name search: %r -> LEI %s (%s) esef=%s",
                    search_name, identity.lei, identity.company_name, best.get("has_esef"),
                )

        # Final currency fix if country was updated
        if identity.country and not detected_currency:
            identity.currency = _COUNTRY_CURRENCY.get(identity.country, "EUR")

        return identity

    @staticmethod
    def _pick_best_gleif_match_with_esef(
        matches: list[dict], search_name: str, http_client
    ) -> dict:
        """
        Like _pick_best_gleif_match but also verifies which LEI has ESEF filings
        on filings.xbrl.org. Candidates with verified ESEF filings are preferred.
        """
        # First pass: score by name similarity (fast)
        candidates = EntityResolver._score_gleif_matches(matches, search_name)

        # Second pass: verify top-3 candidates for ESEF filings (up to 3 HTTP calls)
        _ESEF_BASE = "https://filings.xbrl.org"
        for c in candidates[:3]:
            lei = c["lei"]
            try:
                resp = http_client.get_json(
                    f"{_ESEF_BASE}/api/entities/{lei}/filings"
                )
                items = resp if isinstance(resp, list) else resp.get("filings", resp.get("data", []))
                if items:
                    c["has_esef"] = True
                    logger.info("ESEF verified: LEI %s has %d filings", lei, len(items))
                    return c   # Return immediately — first verified candidate wins
            except Exception:
                pass
            c["has_esef"] = False

        # Fallback: return highest-scored candidate even without ESEF verification
        return candidates[0] if candidates else matches[0]

    @staticmethod
    def _score_gleif_matches(matches: list[dict], search_name: str) -> list[dict]:
        """Score and sort GLEIF matches by name similarity (highest first)."""
        _legal_prefixes = ("SARL ", "SAS ", "SA ", "NV ", "AG ", "GROUPE ", "GROUP ")
        _legal_suffixes = (" SA", " SAS", " NV", " AG", " PLC", " SE", " AB",
                           " ASA", " OY", " BV", " GMBH", " S.A.", " S.P.A.")

        def _core(name: str) -> str:
            n = name.upper().strip()
            for pfx in _legal_prefixes:
                if n.startswith(pfx):
                    n = n[len(pfx):].strip()
            for sfx in _legal_suffixes:
                if n.endswith(sfx):
                    n = n[:-len(sfx)].strip()
            return n

        search_upper = search_name.upper().strip()
        search_core  = _core(search_upper)

        def _score(m: dict) -> tuple:
            legal = (m.get("legal_name") or "").upper().strip()
            if legal == search_upper:             return (4, -len(legal))
            if legal == search_core:              return (4, -len(legal))
            if _core(legal) == search_core:       return (3, -len(legal))
            if _core(legal) == search_upper:      return (2, -len(legal))
            if legal.startswith(search_upper) or legal.startswith(search_core):
                return (1, -len(legal))
            return (0, -len(legal))

        return sorted(matches, key=_score, reverse=True)

    @staticmethod
    def _pick_best_gleif_match(matches: list[dict], search_name: str) -> dict:
        """
        Choose the best GLEIF match from a list by scoring name similarity.

        Scoring (highest wins):
          4 — exact match on full name (case-insensitive)
          3 — core name (after stripping legal suffixes) exactly matches
          2 — legal name equals search_name words in any order
          1 — legal name starts with or contains search_name
          0 — first result (fallback)
        """
        _legal_prefixes = ("SARL ", "SAS ", "SA ", "NV ", "AG ", "GROUPE ", "GROUP ")
        _legal_suffixes = (" SA", " SAS", " NV", " AG", " PLC", " SE", " AB",
                           " ASA", " OY", " BV", " GMBH", " S.A.", " S.P.A.")

        def _core(name: str) -> str:
            n = name.upper().strip()
            for pfx in _legal_prefixes:
                if n.startswith(pfx):
                    n = n[len(pfx):].strip()
            for sfx in _legal_suffixes:
                if n.endswith(sfx):
                    n = n[:-len(sfx)].strip()
            return n

        search_upper = search_name.upper().strip()
        search_core = _core(search_upper)
        # score tuple: (primary_score, -name_length) — prefer higher score, then shorter name
        best_score: tuple = (-1, 0)
        best = matches[0]
        for m in matches:
            legal = (m.get("legal_name") or "").upper().strip()
            if legal == search_upper:
                return m  # exact match wins immediately
            if legal == search_core:
                return m  # exact core match is also unambiguous
            primary = 0
            legal_core = _core(legal)
            if legal_core == search_core:
                primary = 3
            elif legal_core == search_upper:
                primary = 2
            elif legal.startswith(search_upper) or legal.startswith(search_core):
                primary = 1
            score = (primary, -len(legal))   # prefer shorter name when primary is equal
            if score > best_score:
                best_score = score
                best = m
        return best
