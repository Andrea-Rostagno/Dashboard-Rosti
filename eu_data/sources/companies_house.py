"""Companies House UK — official UK company registry. Free API."""
from __future__ import annotations
import base64
from datetime import datetime
from .base               import BaseSource
from ..models.company    import CompanyIdentity
from ..models.filing     import EuropeanFiling
from ..models.financials import NormalizedFinancials
from ..utils.http        import RobustHTTPClient, EUDataHTTPError
from ..utils.logger      import get_logger

logger = get_logger(__name__)
_BASE = "https://api.company-information.service.gov.uk"


class CompaniesHouseSource(BaseSource):
    SOURCE_NAME         = "COMPANIES_HOUSE_UK"
    SUPPORTED_COUNTRIES = ["GB"]

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self._api_key = api_key

    def _auth_headers(self) -> dict:
        if self._api_key:
            creds = base64.b64encode(f"{self._api_key}:".encode()).decode()
            return {"Authorization": f"Basic {creds}"}
        return {}

    def search_company(self, name: str) -> dict | None:
        try:
            data = self._http.get_json(
                f"{_BASE}/search/companies",
                params={"q": name, "items_per_page": 5},
                headers=self._auth_headers(),
            )
            items = data.get("items", [])
            return items[0] if items else None
        except Exception as e:
            logger.warning("Companies House search failed for %s: %s", name, e)
        return None

    def search_filings(
        self,
        company: CompanyIdentity,
        filing_types: list[str] | None = None,
        years_back: int = 5,
    ) -> list[EuropeanFiling]:
        filings: list[EuropeanFiling] = []
        if not company.company_name:
            return filings
        result = self.search_company(company.company_name)
        if not result:
            return filings
        cn = result.get("company_number")
        if not cn:
            return filings
        try:
            data = self._http.get_json(
                f"{_BASE}/company/{cn}/filing-history",
                params={"category": "accounts", "items_per_page": 40},
                headers=self._auth_headers(),
            )
            for item in data.get("items", []):
                desc = (item.get("description") or "").lower()
                if "annual" not in desc and "accounts" not in desc:
                    continue
                dt = item.get("date")
                fy = int(dt[:4]) if dt else None
                if fy and fy < datetime.now().year - years_back:
                    continue
                links = item.get("links", {})
                doc_url = links.get("document_metadata") or links.get("self")
                filings.append(EuropeanFiling(
                    company_id  = company,
                    filing_type = "annual_report",
                    filing_date = datetime.strptime(dt, "%Y-%m-%d").date() if dt else None,
                    fiscal_year = fy,
                    source_name = self.SOURCE_NAME,
                    download_url= doc_url,
                    file_format = "xhtml",
                    raw_metadata= item,
                ))
        except Exception as e:
            logger.warning("Companies House filing history failed: %s", e)
        filings.sort(key=lambda f: f.fiscal_year or 0, reverse=True)
        logger.info("Companies House: %d filings for %s", len(filings), company.company_name)
        return filings

    def download_and_parse(self, filing: EuropeanFiling) -> NormalizedFinancials | None:
        """Companies House documents are not iXBRL — return None (no structured data)."""
        logger.info("CompaniesHouseSource: download_and_parse not implemented for UK filings")
        return None
