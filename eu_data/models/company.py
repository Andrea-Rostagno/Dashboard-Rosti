"""CompanyIdentity dataclass — resolved company metadata."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CompanyIdentity:
    """
    Represents a fully or partially resolved European listed company.

    Fields are populated progressively as resolution APIs are queried:
    OpenFIGI -> GLEIF -> ESEF source.
    """

    ticker: str | None = None
    isin: str | None = None
    lei: str | None = None
    company_name: str | None = None
    country: str | None = None           # ISO-2: "FR", "IT", "DE", "ES", "GB", etc.
    exchange: str | None = None          # "EPA", "BIT", "XETRA", "BME", etc.
    currency: str = "EUR"                # "EUR", "GBP", "CHF", etc.
    confidence: float = 0.0              # 0.0-1.0 match quality
    resolution_source: str = "unknown"  # which API resolved this
    extra_metadata: dict = field(default_factory=dict)

    _CURRENCY_SYM_MAP: dict = field(
        default_factory=lambda: {
            "EUR": "\u20ac", "GBP": "\u00a3", "CHF": "CHF\u00a0",
            "SEK": "kr\u00a0", "DKK": "kr\u00a0", "NOK": "kr\u00a0",
            "PLN": "z\u0142\u00a0", "CZK": "K\u010d\u00a0", "HUF": "Ft\u00a0",
            "USD": "$",
        },
        repr=False, compare=False,
    )

    @property
    def currency_symbol(self) -> str:
        """Return the display symbol for the company's reporting currency."""
        _map = {
            "EUR": "\u20ac", "GBP": "\u00a3", "CHF": "CHF\u00a0",
            "SEK": "kr\u00a0", "DKK": "kr\u00a0", "NOK": "kr\u00a0",
            "PLN": "z\u0142\u00a0", "CZK": "K\u010d\u00a0", "HUF": "Ft\u00a0",
            "USD": "$",
        }
        return _map.get(self.currency, self.currency + "\u00a0")

    def __repr__(self) -> str:
        return (
            f"CompanyIdentity("
            f"ticker={self.ticker!r}, name={self.company_name!r}, "
            f"isin={self.isin!r}, lei={self.lei!r}, "
            f"country={self.country!r}, currency={self.currency!r}, "
            f"confidence={self.confidence:.2f})"
        )
