"""
demo.py — test EU data pipeline with Thales (HO.PA).
Run: python -m eu_data.demo  (from PROGETTO 6 directory)
"""
import sys
sys.path.insert(0, r"D:\Utente\Desktop\QUANT\PROGETTO 6")

from eu_data.pipeline import get_european_company_filings, get_european_financials

_CURRENCY_SYMBOLS = {
    "EUR": "\u20ac",
    "GBP": "\u00a3",
    "CHF": "CHF ",
    "SEK": "SEK ",
    "DKK": "DKK ",
    "NOK": "NOK ",
    "PLN": "PLN ",
    "USD": "$",
}


def currency_symbol(currency: str) -> str:
    return _CURRENCY_SYMBOLS.get(currency, currency + " ")


print("=" * 60)
print("TEST 1 — Company Resolution: Thales (HO.PA)")
print("=" * 60)
company, filings = get_european_company_filings(ticker="HO.PA", years_back=5)
print(f"Name:       {company.company_name}")
print(f"ISIN:       {company.isin}")
print(f"LEI:        {company.lei}")
print(f"Country:    {company.country}")
print(f"Exchange:   {company.exchange}")
print(f"Currency:   {company.currency} ({currency_symbol(company.currency)})")
print(f"Confidence: {company.confidence:.2f}")
print(f"Filings:    {len(filings)}")
for f in filings[:5]:
    print(f"  FY{f.fiscal_year} | {(f.file_format or '?'):>6} | {f.source_name} | {(f.download_url or '')[:80]}")

print()
print("=" * 60)
print("TEST 2 — Financial Data Extraction")
print("=" * 60)
df, filings, company = get_european_financials(ticker="HO.PA", years_back=5)
if df.empty:
    print("No financial data extracted from iXBRL.")
    print("Check filings found above — download URLs may need parsing.")
else:
    cols = ["revenue", "gross_profit", "net_income", "total_assets",
            "equity", "operating_cash_flow", "extraction_quality_score"]
    avail = [c for c in cols if c in df.columns]
    print(df[avail].to_string())
    if "revenue" in df.columns and df["revenue"].notna().any():
        rev = df["revenue"].dropna().iloc[0]
        sym = currency_symbol(company.currency)
        print(f"\nLatest Revenue: {sym}{rev/1e9:.2f}B")
