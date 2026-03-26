"""
Abstract base class for all European financial data sources.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from eu_data.utils.http import RobustHTTPClient
from eu_data.utils.logger import get_logger

if TYPE_CHECKING:
    from eu_data.models.company import CompanyIdentity
    from eu_data.models.filing import EuropeanFiling
    from eu_data.models.financials import NormalizedFinancials


class EUDataError(Exception):
    """Base exception for all eu_data errors."""


class CompanyNotFoundError(EUDataError):
    """Raised when a company cannot be found in a data source."""


class FilingNotFoundError(EUDataError):
    """Raised when no filings are found for a company."""


class ParseError(EUDataError):
    """Raised when a filing document cannot be parsed."""


class BaseSource(ABC):
    """
    Abstract base class for European financial data sources.

    Subclasses implement search_filings() and download_and_parse().
    """

    SOURCE_NAME: str = "UNKNOWN"

    def __init__(self, http_client: RobustHTTPClient | None = None) -> None:
        self._http = http_client or RobustHTTPClient()
        self._logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def search_filings(
        self,
        company: "CompanyIdentity",
        filing_types: list[str] | None = None,
        years_back: int = 5,
    ) -> list["EuropeanFiling"]:
        """
        Search for regulatory filings for the given company.

        Parameters
        ----------
        company : resolved CompanyIdentity
        filing_types : list of types to filter, e.g. ["annual_report"]
        years_back : how many years of history to request

        Returns
        -------
        List of EuropeanFiling objects (may be empty).
        """

    @abstractmethod
    def download_and_parse(
        self, filing: "EuropeanFiling"
    ) -> "NormalizedFinancials | None":
        """
        Download the filing document and parse it into NormalizedFinancials.

        Returns None if parsing fails or no data is available.
        """

    def is_available(self) -> bool:
        """Return True if this source is configured and reachable."""
        return True
