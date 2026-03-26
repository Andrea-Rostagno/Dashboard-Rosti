"""EuropeanFiling dataclass — an official regulatory filing record."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


@dataclass
class EuropeanFiling:
    """
    Represents a single regulatory filing (annual report, half-year, interim)
    from a European OAM, AMF, CNMV, Companies House, or ESEF aggregator.
    """

    company_id: object                    # CompanyIdentity (avoid circular import)
    filing_type: str = "annual_report"    # "annual_report", "half_year", "interim"
    filing_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    fiscal_year: int | None = None
    source_name: str = ""                 # "ESEF_XBRL_ORG", "AMF", "CNMV", "COMPANIES_HOUSE"
    source_url: str | None = None         # webpage / portal URL
    download_url: str | None = None       # direct download URL for the document
    file_format: str | None = None        # "ixbrl", "xhtml", "pdf", "zip", "json"
    language: str | None = None           # "fr", "en", "de", "es", etc.
    raw_metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"EuropeanFiling("
            f"type={self.filing_type!r}, year={self.fiscal_year}, "
            f"end={self.period_end}, format={self.file_format!r}, "
            f"source={self.source_name!r})"
        )
