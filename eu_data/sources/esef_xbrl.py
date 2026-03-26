"""
ESEF primary source via filings.xbrl.org.

filings.xbrl.org aggregates ESEF (European Single Electronic Format) filings
submitted by listed companies to national OAMs (Officially Appointed Mechanisms)
across all EU/EEA member states.

API documentation: https://filings.xbrl.org/api
"""

from __future__ import annotations
import logging
from datetime import date, datetime

from eu_data.models.company import CompanyIdentity
from eu_data.models.filing import EuropeanFiling
from eu_data.models.financials import NormalizedFinancials
from eu_data.parsers.ixbrl_parser import IXBRLParser
from eu_data.parsers.ifrs_tags import FINANCIAL_FIELDS
from eu_data.sources.base import (
    BaseSource,
    CompanyNotFoundError,
    FilingNotFoundError,
    ParseError,
)
from eu_data.utils.http import EUDataHTTPError
from eu_data.utils.logger import get_logger

logger = get_logger(__name__)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _fiscal_year(filing: EuropeanFiling) -> int | None:
    if filing.fiscal_year:
        return filing.fiscal_year
    if filing.period_end:
        return filing.period_end.year
    if filing.period_start:
        return filing.period_start.year
    return None


class ESEFXBRLSource(BaseSource):
    """
    Primary source for all EU publicly listed companies.

    Uses filings.xbrl.org which aggregates ESEF filings from all EU OAMs
    via the ESMA ESEF Reporting Manual mandate.

    Coverage: France, Germany, Italy, Spain, Netherlands, Belgium, Portugal,
    Sweden, Denmark, Finland, Norway, Austria, Ireland, Poland, and more.
    """

    SOURCE_NAME = "ESEF_XBRL_ORG"
    BASE_URL = "https://filings.xbrl.org"

    # Mapping from filings.xbrl.org filing type strings to our standard types
    _TYPE_MAP: dict[str, str] = {
        "annual": "annual_report",
        "annual-report": "annual_report",
        "20-f": "annual_report",
        "10-k": "annual_report",
        "semi-annual": "half_year",
        "half-year": "half_year",
        "quarterly": "interim",
        "interim": "interim",
    }

    def search_filings(
        self,
        company: CompanyIdentity,
        filing_types: list[str] | None = None,
        years_back: int = 5,
    ) -> list[EuropeanFiling]:
        """
        Search filings.xbrl.org for ESEF filings for the given company.

        Searches by LEI first (most accurate), then by company name.
        """
        if filing_types is None:
            filing_types = ["annual_report"]

        filings: list[EuropeanFiling] = []

        # --- Try LEI-based search first ---
        if company.lei:
            filings = self._search_by_lei(company, filing_types, years_back)

        # --- Fallback: name-based search ---
        if not filings and company.company_name:
            filings = self._search_by_name(company, filing_types, years_back)

        return filings

    def _search_by_lei(
        self,
        company: CompanyIdentity,
        filing_types: list[str],
        years_back: int,
    ) -> list[EuropeanFiling]:
        """Search by LEI identifier using the correct /api/entities/{lei}/filings path."""
        # Primary: direct entity endpoint (most reliable)
        url = f"{self.BASE_URL}/api/entities/{company.lei}/filings"
        try:
            resp = self._http.get_json(url)
            if resp:
                return self._parse_response(resp, company, filing_types, years_back)
        except EUDataHTTPError:
            pass

        # Fallback: /api/filings with entity_id param
        for entity_param in ("entity_id", "entity", "lei"):
            try:
                resp = self._http.get_json(
                    f"{self.BASE_URL}/api/filings",
                    params={entity_param: company.lei, "limit": years_back * 3},
                )
                if resp:
                    return self._parse_response(resp, company, filing_types, years_back)
            except EUDataHTTPError:
                continue

        logger.warning("ESEF: no response for LEI %s", company.lei)
        return []

    def _search_by_name(
        self,
        company: CompanyIdentity,
        filing_types: list[str],
        years_back: int,
    ) -> list[EuropeanFiling]:
        """Fallback: search by company name via /api/filings."""
        search_name = company.company_name or ""
        # Use first word of name only if name is long (better precision)
        if len(search_name) > 20:
            search_name = search_name.split()[0]

        # First try entity search then get their filings
        try:
            entity_resp = self._http.get_json(
                f"{self.BASE_URL}/api/entities",
                params={"q": search_name, "limit": 5},
            )
            for ent in self._extract_jsonapi_list(entity_resp):
                attrs = ent.get("attributes", {})
                ent_country = attrs.get("country", "")
                if company.country and ent_country and ent_country.upper() != company.country.upper():
                    continue
                ent_id = ent.get("attributes", {}).get("identifier") or ent.get("id")
                if not ent_id:
                    continue
                try:
                    filings_resp = self._http.get_json(
                        f"{self.BASE_URL}/api/entities/{ent_id}/filings"
                    )
                    result = self._parse_response(filings_resp, company, filing_types, years_back)
                    if result:
                        return result
                except EUDataHTTPError:
                    continue
        except EUDataHTTPError:
            pass

        # Last resort: /api/filings with search param
        for search_param in ("q", "search", "query", "name", "entity_name"):
            try:
                resp = self._http.get_json(
                    f"{self.BASE_URL}/api/filings",
                    params={search_param: search_name, "limit": 20},
                )
                if resp:
                    result = self._parse_response(resp, company, filing_types, years_back)
                    if result:
                        return result
            except EUDataHTTPError:
                continue

        return []

    @staticmethod
    def _extract_jsonapi_list(resp: dict | list) -> list[dict]:
        """Extract items from a JSON:API response (handles both list and {data:[...]} shapes)."""
        if isinstance(resp, list):
            return resp
        if isinstance(resp, dict):
            # JSON:API format: {"data": [...]}
            data = resp.get("data")
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            # Other known keys
            for key in ("filings", "results", "items"):
                if key in resp and isinstance(resp[key], list):
                    return resp[key]
        return []

    def _parse_response(
        self,
        resp: dict | list,
        company: CompanyIdentity,
        filing_types: list[str],
        years_back: int,
    ) -> list[EuropeanFiling]:
        """Parse API response into EuropeanFiling objects."""
        filings_raw: list[dict] = []
        if isinstance(resp, list):
            filings_raw = resp
        elif isinstance(resp, dict):
            for key in ("filings", "data", "results", "items"):
                if key in resp and isinstance(resp[key], list):
                    filings_raw = resp[key]
                    break
            if not filings_raw:
                # Check if the response itself looks like filing data
                if resp.get("id") or resp.get("filing_id"):
                    filings_raw = [resp]

        result: list[EuropeanFiling] = []
        cutoff_year = datetime.now().year - years_back

        for raw in filings_raw:
            if not isinstance(raw, dict):
                continue
            filing = self._dict_to_filing(raw, company)
            if filing is None:
                continue

            # Filter by type
            if "annual_report" in filing_types and filing.filing_type != "annual_report":
                # If we only want annual, skip non-annual
                if filing_types == ["annual_report"]:
                    continue

            # Filter by year
            fy = _fiscal_year(filing)
            if fy and fy < cutoff_year:
                continue

            result.append(filing)

        logger.info(
            "ESEF: found %d filings for %s (LEI=%s)",
            len(result), company.company_name, company.lei,
        )
        return result

    def _dict_to_filing(
        self, raw: dict, company: CompanyIdentity
    ) -> EuropeanFiling | None:
        """Convert a raw API dict to an EuropeanFiling.

        Handles both flat dicts and JSON:API objects where data lives in
        an 'attributes' sub-dict (filings.xbrl.org actual format).
        """
        # JSON:API format: {"type": "filing", "id": "4959", "attributes": {...}}
        attrs = raw.get("attributes", {}) or {}

        # Merge top-level and attributes so both lookups work
        merged = {**attrs, **{k: v for k, v in raw.items() if k != "attributes"}}

        # ID — from top-level "id" or attributes "fxo_id"
        filing_id = (
            raw.get("id")
            or attrs.get("fxo_id")
            or merged.get("filing_id")
            or merged.get("filingId")
            or str(merged.get("pk", ""))
        )

        # Dates — filings.xbrl.org uses "period_end" and "date_added" inside attributes
        period_end = _parse_date(
            attrs.get("period_end")
            or merged.get("period_of_report")
            or merged.get("periodOfReport")
            or merged.get("reportDate")
            or merged.get("period")
        )
        period_start = _parse_date(
            attrs.get("period_start") or merged.get("periodStart")
        )
        filing_date = _parse_date(
            attrs.get("date_added")
            or merged.get("date_filed")
            or merged.get("dateFiled")
            or merged.get("filing_date")
        )

        # Type — JSON:API "type" is "filing" (not the filing type), skip it
        # filings.xbrl.org doesn't expose a filing type field; default to annual_report
        raw_type = (
            attrs.get("report_type", "")
            or attrs.get("documentType", "")
            or attrs.get("form", "")
            or merged.get("report_type", "")
            or merged.get("documentType", "")
            or merged.get("form", "")
        ).lower()
        filing_type = self._TYPE_MAP.get(raw_type, "annual_report")

        # Fiscal year from period end
        fiscal_year = period_end.year if period_end else None
        if not fiscal_year and filing_date:
            fiscal_year = filing_date.year

        # URLs — filings.xbrl.org uses relative paths; prepend BASE_URL
        def _abs(url: str | None) -> str | None:
            if not url:
                return None
            if url.startswith("http"):
                return url
            return f"{self.BASE_URL}{url}"

        viewer_url = _abs(attrs.get("viewer_url") or merged.get("viewer_url"))
        report_url = _abs(attrs.get("report_url") or merged.get("report_url"))
        package_url = _abs(attrs.get("package_url") or merged.get("package_url"))
        json_url    = _abs(attrs.get("json_url") or merged.get("json_url"))

        source_url = viewer_url or report_url or merged.get("source_url") or merged.get("url")

        # Prefer json_url (XBRL JSON, small) over xhtml (large iXBRL) for download
        download_url = (
            json_url
            or report_url
            or package_url
            or merged.get("download_url")
            or merged.get("downloadUrl")
            or merged.get("xbrl_url")
            or merged.get("ixbrl_url")
        )

        # If we have a filing_id but no download_url, construct one
        if filing_id and not download_url:
            download_url = self._get_best_document_url(filing_id)

        # Build source URL from filing_id if missing
        if filing_id and not source_url:
            source_url = f"{self.BASE_URL}/filings/{filing_id}"

        # Format — infer from URL when not explicit
        file_format = merged.get("format") or merged.get("file_format")
        if not file_format and download_url:
            lower = download_url.lower()
            if lower.endswith(".zip"):
                file_format = "zip"
            elif lower.endswith(".xhtml") or lower.endswith(".html"):
                file_format = "ixbrl"
            elif lower.endswith(".pdf"):
                file_format = "pdf"
            elif ".xhtml" in lower or ".html" in lower:
                file_format = "ixbrl"

        # Language
        language = merged.get("language") or merged.get("lang")

        return EuropeanFiling(
            company_id=company,
            filing_type=filing_type,
            filing_date=filing_date,
            period_start=period_start,
            period_end=period_end,
            fiscal_year=fiscal_year,
            source_name=self.SOURCE_NAME,
            source_url=source_url,
            download_url=download_url,
            file_format=file_format or "ixbrl",
            language=language,
            raw_metadata={
                "filing_id": filing_id,
                "json_url_abs": json_url,   # store resolved absolute URL for fallback
                **raw,
            },
        )

    def get_filing_documents(self, filing_id: str) -> list[dict]:
        """
        Retrieve the list of documents for a filing.

        GET /api/filings/{id}/documents
        """
        url = f"{self.BASE_URL}/api/filings/{filing_id}/documents"
        try:
            resp = self._http.get_json(url)
        except EUDataHTTPError as exc:
            logger.warning("Could not get documents for filing %s: %s", filing_id, exc)
            return []

        if isinstance(resp, list):
            return resp
        if isinstance(resp, dict):
            for key in ("documents", "data", "files"):
                if key in resp:
                    return resp[key]
        return []

    def _get_best_document_url(self, filing_id: str) -> str | None:
        """
        Fetch document list for a filing and return the best download URL.
        Preference: ixbrl/xhtml > zip > pdf.
        """
        docs = self.get_filing_documents(filing_id)
        if not docs:
            return None

        preference = ["ixbrl", "xbrl", "xhtml", "zip", "html", "pdf"]
        scored: list[tuple[int, str]] = []

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            url = (
                doc.get("url")
                or doc.get("download_url")
                or doc.get("href")
                or doc.get("path")
                or ""
            )
            fmt = (doc.get("format") or doc.get("type") or "").lower()
            if not fmt and url:
                lower = url.lower()
                for f in preference:
                    if f in lower:
                        fmt = f
                        break
            try:
                score = preference.index(fmt)
            except ValueError:
                score = len(preference)
            if url:
                scored.append((score, url))

        if scored:
            scored.sort(key=lambda x: x[0])
            return scored[0][1]
        return None

    def download_and_parse(
        self, filing: EuropeanFiling
    ) -> NormalizedFinancials | None:
        """
        Download the iXBRL document and parse it into NormalizedFinancials.

        Tries the download_url directly; if not available, queries the
        documents endpoint for the best document URL.
        """
        filing_id = filing.raw_metadata.get("filing_id", "")

        # Ensure we have a download URL
        dl_url = filing.download_url
        if not dl_url and filing_id:
            dl_url = self._get_best_document_url(str(filing_id))
            if dl_url:
                filing.download_url = dl_url

        if not dl_url:
            logger.warning(
                "No download URL for filing %s (%s)", filing_id, filing.period_end
            )
            # Try the facts API as a last resort
            return self._parse_via_facts_api(filing)

        logger.info("Downloading ESEF document: %s", dl_url)

        # If URL ends in .json, parse as XBRL JSON (more reliable, compact)
        if dl_url.lower().endswith(".json"):
            return self._parse_xbrl_json_url(dl_url, filing)

        try:
            raw_bytes = self._http.download_binary(dl_url)
        except EUDataHTTPError as exc:
            logger.warning("Download failed for %s: %s — trying JSON fallback", dl_url, exc)
            # Try the json_url from raw_metadata if available
            json_url = filing.raw_metadata.get("json_url_abs")
            if json_url:
                return self._parse_xbrl_json_url(json_url, filing)
            return None

        # Parse iXBRL
        parser = IXBRLParser(http_client=self._http)
        try:
            facts = parser.parse_from_bytes(
                raw_bytes,
                filename=dl_url.split("/")[-1].split("?")[0],
            )
        except Exception as exc:
            logger.warning("iXBRL parse error for %s: %s — no fallback available", dl_url, exc)
            return None

        if not facts:
            logger.warning("No facts extracted from %s", dl_url)
            return None

        year = filing.fiscal_year or (
            filing.period_end.year if filing.period_end else None
        )
        annual_data = parser.to_annual_financials(facts, year=year)
        return self._dict_to_normalized(annual_data, filing, source="ixbrl_download")

    def _parse_xbrl_json_url(
        self, json_url: str, filing: EuropeanFiling
    ) -> NormalizedFinancials | None:
        """
        Download and parse a filings.xbrl.org XBRL JSON file.

        The XBRL JSON format (OIM) has structure:
          {"documentInfo": {...}, "facts": {"f-1": {"value": ..., "dimensions": {...}}, ...}}
        """
        logger.info("Parsing XBRL JSON: %s", json_url)
        try:
            resp = self._http.get_json(json_url, timeout=60)
        except EUDataHTTPError as exc:
            logger.warning("XBRL JSON download failed for %s: %s", json_url, exc)
            return None

        facts_raw = resp.get("facts", {}) if isinstance(resp, dict) else {}
        if not facts_raw:
            return None

        data = self._extract_from_xbrl_json_facts(facts_raw, filing)
        if not data:
            return None
        return self._dict_to_normalized(data, filing, source="xbrl_json")

    def _extract_from_xbrl_json_facts(
        self, facts_raw: dict, filing: EuropeanFiling
    ) -> dict:
        """
        Extract IFRS financials from XBRL JSON OIM facts dict.

        Each fact: {"value": ..., "dimensions": {"concept": "ifrs-full:Revenue",
                   "period": "2022-01-01T.../2023-01-01T...", "entity": ...}}

        We pick the best (most recent annual, no extra dimensions) value per concept.
        """
        from eu_data.parsers.ifrs_tags import IFRS_TO_FIELD, IFRS_SHORT_NAMES

        result: dict[str, float] = {}
        # concept -> list of (value, period_end_str, n_extra_dims)
        concept_candidates: dict[str, list] = {}

        filing_year = filing.fiscal_year or 0

        for _fid, fact in facts_raw.items():
            if not isinstance(fact, dict):
                continue
            dims = fact.get("dimensions", {})
            concept = dims.get("concept", "")
            value = fact.get("value")
            if not concept or value is None:
                continue
            try:
                fval = float(value)
            except (ValueError, TypeError):
                continue

            # Skip dimensional breakdowns (more than concept+period+entity = 3 dims)
            n_dims = len(dims)
            period = str(dims.get("period", ""))

            concept_candidates.setdefault(concept, []).append(
                (fval, period, n_dims)
            )

        for concept, candidates in concept_candidates.items():
            field = IFRS_TO_FIELD.get(concept)
            if not field:
                short = concept.split(":")[-1]
                field = IFRS_SHORT_NAMES.get(short)
            if not field or field in result:
                continue

            # Prefer: non-dimensional (n_dims==3), then latest period
            # Filter to annual periods (period contains '/' = duration)
            annual = [c for c in candidates if "/" in c[1] and c[2] <= 3]
            if not annual:
                annual = [c for c in candidates if c[2] <= 3]
            if not annual:
                annual = candidates

            # Pick fewest extra dims first, then most recent period
            _min_dims = min(c[2] for c in annual)
            _best_cands = [c for c in annual if c[2] == _min_dims]
            best_val = sorted(_best_cands, key=lambda x: x[1], reverse=True)[0][0]
            result[field] = best_val

        return result

    def _parse_via_facts_api(
        self, filing: EuropeanFiling
    ) -> NormalizedFinancials | None:
        """
        Fallback: use the filings.xbrl.org facts JSON API instead of downloading raw iXBRL.
        """
        filing_id = filing.raw_metadata.get("filing_id", "")
        if not filing_id:
            return None

        url = f"{self.BASE_URL}/api/filings/{filing_id}/facts"
        try:
            facts_json = self._http.get_json(url, timeout=30)
        except EUDataHTTPError as exc:
            logger.warning("Facts API failed for filing %s: %s", filing_id, exc)
            return None

        data = self._extract_from_facts_json(facts_json)
        if not data:
            return None
        return self._dict_to_normalized(data, filing, source="facts_api")

    def _extract_from_facts_json(self, facts_json: dict | list) -> dict:
        """Extract IFRS field values from the filings.xbrl.org facts JSON response."""
        from eu_data.parsers.ifrs_tags import IFRS_TO_FIELD, IFRS_SHORT_NAMES

        result: dict[str, float] = {}

        facts_list: list = []
        if isinstance(facts_json, list):
            facts_list = facts_json
        elif isinstance(facts_json, dict):
            for key in ("facts", "data", "items", "values"):
                if key in facts_json and isinstance(facts_json[key], list):
                    facts_list = facts_json[key]
                    break

        if not facts_list:
            return result

        # Group by concept → pick most recent annual value
        concept_candidates: dict[str, list] = {}
        for fact in facts_list:
            if not isinstance(fact, dict):
                continue
            concept = (
                fact.get("concept")
                or fact.get("conceptName")
                or fact.get("name")
                or ""
            )
            value = fact.get("value") or fact.get("numericValue") or fact.get("doubleValue")
            period = str(fact.get("period") or fact.get("endDate") or fact.get("instant") or "")
            if not concept or value is None:
                continue
            try:
                fval = float(value)
            except (ValueError, TypeError):
                continue
            concept_candidates.setdefault(concept, []).append((fval, period))

        for concept, candidates in concept_candidates.items():
            # Match to field
            field = IFRS_TO_FIELD.get(concept)
            if not field:
                short = concept.split(":")[-1]
                field = IFRS_SHORT_NAMES.get(short)
            if not field or field in result:
                continue
            # Pick the most recent period
            best_val, _ = sorted(candidates, key=lambda x: x[1], reverse=True)[0]
            result[field] = best_val

        return result

    def _dict_to_normalized(
        self,
        data: dict,
        filing: EuropeanFiling,
        source: str = "",
    ) -> NormalizedFinancials | None:
        """Convert a {field: value} dict to NormalizedFinancials."""
        if not data:
            return None

        company = filing.company_id
        year = _fiscal_year(filing) or datetime.now().year
        currency = (
            data.get("currency")
            or (company.currency if hasattr(company, "currency") else "EUR")
        )

        # Count how many key financial fields we managed to extract
        key_fields = [
            "revenue", "net_income", "total_assets", "equity",
            "operating_cash_flow", "operating_income",
        ]
        filled = sum(1 for f in key_fields if data.get(f) is not None)
        quality = min(1.0, filled / len(key_fields))

        # Derive gross_profit if not explicit
        gross_profit = data.get("gross_profit")
        if gross_profit is None:
            rev = data.get("revenue")
            cogs = data.get("cost_of_revenue")
            if rev is not None and cogs is not None:
                gross_profit = rev - abs(cogs)

        # Derive total_liabilities if not explicit (assets - equity)
        total_liabilities = data.get("total_liabilities")
        if total_liabilities is None:
            ta = data.get("total_assets")
            eq = data.get("equity")
            if ta is not None and eq is not None:
                total_liabilities = ta - eq

        # Derive EBITDA if not explicit
        ebitda = data.get("ebitda")
        if ebitda is None:
            op_inc = data.get("operating_income")
            da = data.get("depreciation_amortization")
            if op_inc is not None and da is not None:
                ebitda = op_inc + abs(da)

        # Derive free cash flow if not explicit
        fcf = data.get("free_cash_flow")
        if fcf is None:
            ocf = data.get("operating_cash_flow")
            capex = data.get("capex")
            if ocf is not None and capex is not None:
                fcf = ocf - abs(capex)

        nf = NormalizedFinancials(
            company_identity=company,
            filing=filing,
            fiscal_year=year,
            currency=currency,
            revenue=data.get("revenue"),
            gross_profit=gross_profit,
            operating_income=data.get("operating_income"),
            ebitda=ebitda,
            net_income=data.get("net_income"),
            interest_expense=data.get("interest_expense"),
            income_tax=data.get("income_tax"),
            total_assets=data.get("total_assets"),
            total_liabilities=total_liabilities,
            equity=data.get("equity"),
            cash_and_equivalents=data.get("cash_and_equivalents"),
            long_term_debt=data.get("long_term_debt"),
            short_term_debt=data.get("short_term_debt"),
            current_assets=data.get("current_assets"),
            current_liabilities=data.get("current_liabilities"),
            operating_cash_flow=data.get("operating_cash_flow"),
            investing_cash_flow=data.get("investing_cash_flow"),
            financing_cash_flow=data.get("financing_cash_flow"),
            capex=data.get("capex"),
            free_cash_flow=fcf,
            shares_outstanding=data.get("shares_outstanding"),
            extraction_quality_score=quality,
            raw_source_metadata={
                "source": source,
                "filing_id": filing.raw_metadata.get("filing_id", ""),
                "fields_found": list(data.keys()),
            },
        )
        return nf
