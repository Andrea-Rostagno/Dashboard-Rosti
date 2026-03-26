"""NormalizedFinancials dataclass — standardised financial data from any EU source."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from eu_data.models.company import CompanyIdentity
    from eu_data.models.filing import EuropeanFiling


@dataclass
class NormalizedFinancials:
    """
    Normalized financial data extracted from an ESEF/IFRS filing.
    All monetary values are in the company's reporting currency (see `currency`).
    All monetary values are in full units (not thousands/millions) unless noted.
    """

    company_identity: object              # CompanyIdentity
    filing: object | None = None          # EuropeanFiling | None
    fiscal_year: int = 0
    currency: str = "EUR"

    # ── Income Statement ─────────────────────────────────────────────────────
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None     # EBIT
    ebitda: float | None = None
    net_income: float | None = None
    interest_expense: float | None = None
    income_tax: float | None = None

    # ── Balance Sheet ────────────────────────────────────────────────────────
    total_assets: float | None = None
    total_liabilities: float | None = None
    equity: float | None = None
    cash_and_equivalents: float | None = None
    long_term_debt: float | None = None
    short_term_debt: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None

    # ── Cash Flow Statement ──────────────────────────────────────────────────
    operating_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None

    # ── Per Share ────────────────────────────────────────────────────────────
    shares_outstanding: float | None = None

    # ── Quality / Provenance ─────────────────────────────────────────────────
    extraction_quality_score: float = 0.0    # 0.0-1.0
    raw_source_metadata: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        """Return all fields as a flat dictionary suitable for DataFrame construction."""
        return {
            "fiscal_year": self.fiscal_year,
            "currency": self.currency,
            "revenue": self.revenue,
            "gross_profit": self.gross_profit,
            "operating_income": self.operating_income,
            "ebitda": self.ebitda,
            "net_income": self.net_income,
            "interest_expense": self.interest_expense,
            "income_tax": self.income_tax,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "equity": self.equity,
            "cash_and_equivalents": self.cash_and_equivalents,
            "long_term_debt": self.long_term_debt,
            "short_term_debt": self.short_term_debt,
            "current_assets": self.current_assets,
            "current_liabilities": self.current_liabilities,
            "operating_cash_flow": self.operating_cash_flow,
            "investing_cash_flow": self.investing_cash_flow,
            "financing_cash_flow": self.financing_cash_flow,
            "capex": self.capex,
            "free_cash_flow": self.free_cash_flow,
            "shares_outstanding": self.shares_outstanding,
            "extraction_quality_score": self.extraction_quality_score,
        }

    def to_dataframe_row(self) -> pd.Series:
        """Return a pandas Series indexed by field name, with fiscal_year as name."""
        d = self.to_dict()
        year = d.pop("fiscal_year")
        s = pd.Series(d, name=year)
        return s

    def __repr__(self) -> str:
        name = getattr(self.company_identity, "company_name", "?")
        return (
            f"NormalizedFinancials("
            f"company={name!r}, year={self.fiscal_year}, "
            f"currency={self.currency!r}, "
            f"revenue={self.revenue}, net_income={self.net_income}, "
            f"quality={self.extraction_quality_score:.2f})"
        )
