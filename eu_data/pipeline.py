"""
eu_data.pipeline — high-level public API.

Usage:
    from eu_data.pipeline import get_european_financials, get_european_company_filings
    df, filings, company = get_european_financials("HO.PA", years_back=5)
"""
from __future__ import annotations
import pandas as pd
from .resolvers.resolver import EntityResolver
from .sources.router     import SourceRouter
from .models.company     import CompanyIdentity
from .models.filing      import EuropeanFiling
from .models.financials  import NormalizedFinancials
from .utils.logger       import get_logger

logger = get_logger(__name__)


def get_european_company_filings(
    ticker: str | None = None,
    isin: str | None = None,
    company_name: str | None = None,
    country: str | None = None,
    years_back: int = 5,
    companies_house_api_key: str | None = None,
    openfigi_api_key: str | None = None,
) -> tuple[CompanyIdentity, list[EuropeanFiling]]:
    """Resolve company identity and return list of available official filings."""
    resolver = EntityResolver(openfigi_api_key=openfigi_api_key)
    company  = resolver.resolve(ticker=ticker, isin=isin, company_name=company_name)
    if country:
        company.country = country.upper()

    router  = SourceRouter(companies_house_api_key=companies_house_api_key)
    sources = router.get_sources(company.country)

    all_filings: list[EuropeanFiling] = []
    for source in sources:
        try:
            found = source.search_filings(company, years_back=years_back)
            all_filings.extend(found)
            if found:
                logger.info("%s found %d filings", source.SOURCE_NAME, len(found))
        except Exception as e:
            logger.warning("Source %s failed: %s", source.SOURCE_NAME, e)

    seen: set = set()
    unique: list[EuropeanFiling] = []
    for f in all_filings:
        key = (f.fiscal_year, f.source_name)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    unique.sort(key=lambda f: f.fiscal_year or 0, reverse=True)
    logger.info("Total unique filings: %d for %s", len(unique), company.company_name or ticker)
    return company, unique


def get_european_financials(
    ticker: str | None = None,
    isin: str | None = None,
    company_name: str | None = None,
    country: str | None = None,
    years_back: int = 5,
    companies_house_api_key: str | None = None,
    openfigi_api_key: str | None = None,
) -> tuple[pd.DataFrame, list[EuropeanFiling], CompanyIdentity]:
    """
    Fetch normalised financial data for a European listed company.

    Returns (df, filings, company) where df is indexed by fiscal_year.
    """
    company, filings = get_european_company_filings(
        ticker=ticker, isin=isin, company_name=company_name,
        country=country, years_back=years_back,
        companies_house_api_key=companies_house_api_key,
        openfigi_api_key=openfigi_api_key,
    )

    router  = SourceRouter(companies_house_api_key=companies_house_api_key)
    sources = router.get_sources(company.country)

    # Build a lookup: source_name -> source instance
    source_map = {s.SOURCE_NAME: s for s in sources}

    rows: list[NormalizedFinancials] = []
    processed: set[int] = set()

    for filing in filings:
        if filing.fiscal_year in processed:
            continue
        # Try the source that produced this filing first, then others
        ordered_sources = []
        if filing.source_name in source_map:
            ordered_sources.append(source_map[filing.source_name])
        for s in sources:
            if s not in ordered_sources:
                ordered_sources.append(s)

        for source in ordered_sources:
            try:
                fin = source.download_and_parse(filing)
                if fin and fin.revenue is not None:
                    rows.append(fin)
                    processed.add(fin.fiscal_year)
                    logger.info("FY%s extracted | quality=%.2f",
                                fin.fiscal_year, fin.extraction_quality_score)
                    break
            except Exception as e:
                logger.warning("download_and_parse failed FY%s: %s",
                               filing.fiscal_year, e)

    if not rows:
        logger.warning("No financial data for %s", company.company_name or ticker)
        return pd.DataFrame(), filings, company

    df = pd.DataFrame([r.to_dict() for r in rows])
    df = df.set_index("fiscal_year").sort_index(ascending=False)
    # Convert all non-string columns to float (None → NaN), ensuring abs() works
    _skip_cols = {"currency"}
    for col in df.columns:
        if col not in _skip_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df, filings, company
