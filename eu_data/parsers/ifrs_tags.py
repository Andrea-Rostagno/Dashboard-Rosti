"""
IFRS taxonomy tag-to-field mapping.

Covers the most common IFRS Full taxonomy elements used in ESEF filings.
Custom company namespace tags fall back to short name matching via IFRS_SHORT_NAMES.
"""

from __future__ import annotations


IFRS_TO_FIELD: dict[str, str] = {
    # ── Revenue ────────────────────────────────────────────────────────────
    "ifrs-full:Revenue": "revenue",
    "ifrs-full:RevenueFromContractsWithCustomers": "revenue",
    "ifrs-full:SalesRevenueNet": "revenue",
    "ifrs-full:SalesAndOtherOperatingRevenue": "revenue",
    "ifrs-full:RevenueFromSaleOfGoods": "revenue",
    "ifrs-full:RevenueFromRenderingOfServices": "revenue",
    "ifrs-full:TurnoverRevenue": "revenue",
    "ifrs-full:NetRevenue": "revenue",
    # ── Gross Profit / Cost of Sales ─────────────────────────────────────
    "ifrs-full:GrossProfit": "gross_profit",
    "ifrs-full:CostOfSales": "cost_of_revenue",
    "ifrs-full:CostOfGoodsSold": "cost_of_revenue",
    "ifrs-full:CostOfRevenue": "cost_of_revenue",
    # ── Operating Income (EBIT) ────────────────────────────────────────────
    "ifrs-full:ProfitLossFromOperatingActivities": "operating_income",
    "ifrs-full:OperatingIncomeLoss": "operating_income",
    "ifrs-full:OperatingProfit": "operating_income",
    "ifrs-full:ProfitBeforeFinancialItemsAndTax": "operating_income",
    "ifrs-full:ResultFromOperatingActivities": "operating_income",
    # ── EBITDA / D&A ──────────────────────────────────────────────────────
    "ifrs-full:DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss": "depreciation_amortization",
    "ifrs-full:DepreciationAndAmortisationExpense": "depreciation_amortization",
    "ifrs-full:AdjustmentsForDepreciationAndAmortisationExpense": "depreciation_amortization",
    "ifrs-full:AdjustmentsForDepreciationAmortisationAndImpairmentLoss": "depreciation_amortization",
    "ifrs-full:DepreciationExpense": "depreciation_amortization",
    "ifrs-full:AmortisationExpense": "depreciation_amortization",
    # ── Net Income ────────────────────────────────────────────────────────
    "ifrs-full:ProfitLoss": "net_income",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent": "net_income",
    "ifrs-full:NetProfitLoss": "net_income",
    "ifrs-full:ProfitLossBeforeTax": "profit_before_tax",
    "ifrs-full:ComprehensiveIncome": "net_income",
    # ── Interest & Finance ───────────────────────────────────────────────
    "ifrs-full:FinanceCosts": "interest_expense",
    "ifrs-full:InterestExpense": "interest_expense",
    "ifrs-full:InterestPaidClassifiedAsOperatingActivities": "interest_expense",
    "ifrs-full:InterestPaidClassifiedAsFinancingActivities": "interest_expense",
    "ifrs-full:FinanceIncome": "finance_income",
    "ifrs-full:FinanceIncomeExpense": "net_finance_costs",
    # ── Tax ─────────────────────────────────────────────────────────────
    "ifrs-full:IncomeTaxExpenseContinuingOperations": "income_tax",
    "ifrs-full:TaxExpense": "income_tax",
    "ifrs-full:CurrentTaxExpenseIncome": "income_tax",
    # ── Balance Sheet Assets ─────────────────────────────────────────────
    "ifrs-full:Assets": "total_assets",
    "ifrs-full:TotalAssets": "total_assets",
    "ifrs-full:CurrentAssets": "current_assets",
    "ifrs-full:NoncurrentAssets": "noncurrent_assets",
    "ifrs-full:CashAndCashEquivalents": "cash_and_equivalents",
    "ifrs-full:CashAndBankBalancesAtCentralBanks": "cash_and_equivalents",
    "ifrs-full:TradeAndOtherCurrentReceivables": "receivables",
    "ifrs-full:Inventories": "inventories",
    "ifrs-full:PropertyPlantAndEquipment": "ppe",
    "ifrs-full:GoodwillAndIntangibleAssets": "goodwill_intangibles",
    "ifrs-full:Goodwill": "goodwill",
    "ifrs-full:IntangibleAssetsOtherThanGoodwill": "intangible_assets",
    # ── Balance Sheet Liabilities ─────────────────────────────────────────
    "ifrs-full:Liabilities": "total_liabilities",
    "ifrs-full:TotalLiabilities": "total_liabilities",
    "ifrs-full:CurrentLiabilities": "current_liabilities",
    "ifrs-full:NoncurrentLiabilities": "noncurrent_liabilities",
    "ifrs-full:NoncurrentPortionOfLongtermBorrowings": "long_term_debt",
    "ifrs-full:LongtermBorrowings": "long_term_debt",
    "ifrs-full:Borrowings": "total_borrowings",
    "ifrs-full:CurrentPortionOfLongtermBorrowings": "short_term_debt",
    "ifrs-full:ShorttermBorrowings": "short_term_debt",
    "ifrs-full:TradeAndOtherCurrentPayables": "trade_payables",
    # ── Equity ───────────────────────────────────────────────────────────
    "ifrs-full:Equity": "equity",
    "ifrs-full:EquityAttributableToOwnersOfParent": "equity",
    "ifrs-full:TotalEquity": "equity",
    "ifrs-full:IssuedCapital": "share_capital",
    "ifrs-full:RetainedEarnings": "retained_earnings",
    # ── Cash Flow Statement ──────────────────────────────────────────────
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "operating_cash_flow",
    "ifrs-full:NetCashFlowsFromOperatingActivities": "operating_cash_flow",
    "ifrs-full:CashFlowsFromUsedInInvestingActivities": "investing_cash_flow",
    "ifrs-full:NetCashFlowsFromInvestingActivities": "investing_cash_flow",
    "ifrs-full:CashFlowsFromUsedInFinancingActivities": "financing_cash_flow",
    "ifrs-full:NetCashFlowsFromFinancingActivities": "financing_cash_flow",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "capex",
    "ifrs-full:AcquisitionOfPropertyPlantAndEquipment": "capex",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipment": "capex",
    "ifrs-full:AcquisitionOfPropertyPlantAndEquipmentIntangibleAssetsAndOtherLongtermAssets": "capex",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets": "capex",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentAndIntangibleAssets": "capex",
    "ifrs-full:AcquisitionOfPropertyPlantAndEquipmentAndIntangibleAssets": "capex",
    "ifrs-full:ProceedsFromIssuanceOfEquityInstruments": "equity_issuance_proceeds",
    "ifrs-full:DividendsPaid": "dividends_paid",
    "ifrs-full:DividendsPaidClassifiedAsFinancingActivities": "dividends_paid",
    "ifrs-full:DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities": "dividends_paid",
    "ifrs-full:DividendsPaidToNoncontrollingInterestsClassifiedAsFinancingActivities": "dividends_paid",
    "ifrs-full:IncreaseThroughNewIssues": "dividends_paid",
    # ── Per share ────────────────────────────────────────────────────────
    "ifrs-full:WeightedAverageShares": "shares_outstanding",
    "ifrs-full:WeightedAverageNumberOfOrdinarySharesOutstanding": "shares_outstanding",
    "ifrs-full:NumberOfSharesOutstanding": "shares_outstanding",
    "ifrs-full:NumberOfSharesIssuedAndFullyPaid": "shares_outstanding",
    "ifrs-full:BasicEarningsLossPerShare": "eps_basic",
    "ifrs-full:DilutedEarningsLossPerShare": "eps_diluted",
    # ── Sector-specific / additional ─────────────────────────────────────
    "ifrs-full:InsurancePremiumsEarned": "revenue",           # Insurance
    "ifrs-full:InterestAndFeeIncomeOnLoansAndAdvances": "revenue",  # Banking
    "ifrs-full:FeeAndCommissionIncome": "revenue",            # Banking
    "ifrs-full:NetInterestIncome": "revenue",                 # Banking
    # ── dei: namespace (US but appears in some EU filings) ───────────────
    "dei:EntityCommonStockSharesOutstanding": "shares_outstanding",
}


# Short-name lookup (namespace-stripped) for fuzzy matching of company namespaces.
# e.g. "thales-2024:Revenue" → strip to "Revenue" → map to "revenue"
IFRS_SHORT_NAMES: dict[str, str] = {}
for _tag, _field in IFRS_TO_FIELD.items():
    _short = _tag.split(":")[-1]
    # Prefer the first mapping if multiple tags share the same short name
    if _short not in IFRS_SHORT_NAMES:
        IFRS_SHORT_NAMES[_short] = _field

# Additional common short-name aliases that appear in real filings
_EXTRA_SHORT: dict[str, str] = {
    "Revenue": "revenue",
    "Revenues": "revenue",
    "TotalRevenue": "revenue",
    "NetRevenue": "revenue",
    "GrossProfit": "gross_profit",
    "OperatingProfit": "operating_income",
    "EBIT": "operating_income",
    "EBITDA": "ebitda",
    "ProfitAfterTax": "net_income",
    "NetProfit": "net_income",
    "NetIncome": "net_income",
    "TotalAssets": "total_assets",
    "TotalLiabilities": "total_liabilities",
    "TotalEquity": "equity",
    "ShareholdersEquity": "equity",
    "CashAndCashEquivalents": "cash_and_equivalents",
    "LongTermDebt": "long_term_debt",
    "ShortTermDebt": "short_term_debt",
    "CurrentAssets": "current_assets",
    "CurrentLiabilities": "current_liabilities",
    "OperatingCashFlow": "operating_cash_flow",
    "InvestingCashFlow": "investing_cash_flow",
    "FinancingCashFlow": "financing_cash_flow",
    "CapitalExpenditure": "capex",
    "Capex": "capex",
    "FreeCashFlow": "free_cash_flow",
    "SharesOutstanding": "shares_outstanding",
    "InterestExpense": "interest_expense",
    "IncomeTax": "income_tax",
    "TaxExpense": "income_tax",
    "Depreciation": "depreciation_amortization",
    "Amortization": "depreciation_amortization",
}
IFRS_SHORT_NAMES.update(_EXTRA_SHORT)


# Fields that map directly to NormalizedFinancials attributes
FINANCIAL_FIELDS: set[str] = {
    "revenue",
    "gross_profit",
    "cost_of_revenue",
    "operating_income",
    "ebitda",
    "net_income",
    "interest_expense",
    "income_tax",
    "total_assets",
    "total_liabilities",
    "equity",
    "cash_and_equivalents",
    "long_term_debt",
    "short_term_debt",
    "current_assets",
    "current_liabilities",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "capex",
    "free_cash_flow",
    "shares_outstanding",
    "depreciation_amortization",
}
