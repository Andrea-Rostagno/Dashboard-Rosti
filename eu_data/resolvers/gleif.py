"""
GLEIF (Global LEI Foundation) resolver.

Maps ISIN → LEI (Legal Entity Identifier) and fetches official company metadata.

API: https://api.gleif.org/api/v1/
Free, no authentication required. Rate limit: 60 req/min.
"""

from __future__ import annotations
import logging

from eu_data.utils.http import RobustHTTPClient, EUDataHTTPError
from eu_data.utils.logger import get_logger

logger = get_logger(__name__)


class GLEIFResolver:
    """
    Resolve ISIN codes to LEI and retrieve company entity data via GLEIF API.

    GLEIF is the official global registry of Legal Entity Identifiers,
    managed under the authority of the Financial Stability Board (FSB).
    """

    BASE_URL = "https://api.gleif.org/api/v1"

    def __init__(self, http_client: RobustHTTPClient | None = None) -> None:
        self._http = http_client or RobustHTTPClient()

    def get_lei_from_isin(self, isin: str) -> str | None:
        """
        Look up the LEI for a given ISIN.

        Parameters
        ----------
        isin : e.g. "FR0000131104"

        Returns
        -------
        LEI string (20-character alphanumeric) or None if not found.
        """
        url = f"{self.BASE_URL}/lei-records"
        try:
            data = self._http.get_json(
                url,
                params={"filter[isin]": isin, "page[size]": 1},
            )
        except EUDataHTTPError as exc:
            logger.warning("GLEIF ISIN lookup failed for %s: %s", isin, exc)
            return None

        records = data.get("data", [])
        if not records:
            logger.debug("GLEIF: no LEI found for ISIN %s", isin)
            return None

        lei = records[0].get("id") or (
            records[0].get("attributes", {}).get("lei")
        )
        logger.info("GLEIF: ISIN %s → LEI %s", isin, lei)
        return lei

    def get_company_info(self, lei: str) -> dict | None:
        """
        Fetch entity metadata for a given LEI.

        Parameters
        ----------
        lei : 20-character Legal Entity Identifier

        Returns
        -------
        dict with keys:
            lei, legal_name, country, jurisdiction, status,
            registered_address, business_register_id, category
        or None on failure.
        """
        url = f"{self.BASE_URL}/lei-records/{lei}"
        try:
            data = self._http.get_json(url)
        except EUDataHTTPError as exc:
            logger.warning("GLEIF entity lookup failed for LEI %s: %s", lei, exc)
            return None

        record = data.get("data", {})
        if not record:
            return None

        attrs = record.get("attributes", {})
        entity = attrs.get("entity", {})
        legal_name_obj = entity.get("legalName", {})

        # Extract jurisdiction country code
        jurisdiction = entity.get("jurisdiction", "")
        country = jurisdiction[:2].upper() if jurisdiction else ""

        # Legal name
        legal_name = (
            legal_name_obj.get("name", "")
            if isinstance(legal_name_obj, dict)
            else str(legal_name_obj)
        )

        # Registered address
        reg_addr = entity.get("legalAddress", {}) or {}
        country_from_addr = reg_addr.get("country", "")
        if not country and country_from_addr:
            country = country_from_addr[:2].upper()

        result = {
            "lei": record.get("id", lei),
            "legal_name": legal_name,
            "country": country,
            "jurisdiction": jurisdiction,
            "status": attrs.get("registration", {}).get("status", ""),
            "registered_address": {
                "street": reg_addr.get("addressLines", []),
                "city": reg_addr.get("city", ""),
                "postal_code": reg_addr.get("postalCode", ""),
                "country": reg_addr.get("country", ""),
            },
            "business_register_id": attrs.get("registration", {}).get(
                "businessRegisterEntityID", ""
            ),
            "category": entity.get("category", ""),
            "entity_status": entity.get("entityStatus", ""),
        }
        return result

    def search_by_name(self, name: str, country: str | None = None) -> list[dict]:
        """
        Search GLEIF by legal entity name.

        Parameters
        ----------
        name : company name to search
        country : optional ISO-2 country code to filter results

        Returns
        -------
        list of dicts (up to 5 best matches) with keys: lei, legal_name, country
        """
        url = f"{self.BASE_URL}/lei-records"
        params: dict = {
            "filter[entity.names]": name,
            "page[size]": 10,
        }
        if country:
            params["filter[entity.legalAddress.country]"] = country.upper()

        try:
            data = self._http.get_json(url, params=params)
        except EUDataHTTPError as exc:
            logger.warning("GLEIF name search failed for %r: %s", name, exc)
            return []

        results = []
        for record in data.get("data", [])[:5]:
            attrs = record.get("attributes", {})
            entity = attrs.get("entity", {})
            legal_name_obj = entity.get("legalName", {})
            legal_name = (
                legal_name_obj.get("name", "")
                if isinstance(legal_name_obj, dict)
                else str(legal_name_obj)
            )
            jur = entity.get("jurisdiction", "")
            results.append({
                "lei": record.get("id", ""),
                "legal_name": legal_name,
                "country": jur[:2].upper() if jur else "",
            })
        return results
