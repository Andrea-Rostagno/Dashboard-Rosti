"""CNMV Spain — supplement source (stub, ESEF is primary for ES companies)."""
from __future__ import annotations
from .base               import BaseSource
from ..models.company    import CompanyIdentity
from ..models.filing     import EuropeanFiling
from ..models.financials import NormalizedFinancials
from ..utils.logger      import get_logger

logger = get_logger(__name__)


class CNMVSpainSource(BaseSource):
    SOURCE_NAME         = "CNMV_ES"
    SUPPORTED_COUNTRIES = ["ES"]

    def search_filings(
        self,
        company: CompanyIdentity,
        filing_types: list[str] | None = None,
        years_back: int = 5,
    ) -> list[EuropeanFiling]:
        """CNMV stub — ESEF source is primary for ES companies."""
        logger.info("CNMVSpainSource: delegating to ESEF for %s", company.company_name)
        return []

    def download_and_parse(self, filing: EuropeanFiling) -> NormalizedFinancials | None:
        """Not implemented — ESEF handles downloads for ES companies."""
        return None
