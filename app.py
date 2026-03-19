"""
Analisi Fondamentale v3 — Streamlit App
========================================
Navigazione a tab, UI glassmorphism, dark theme professionale.
Dati: SEC EDGAR (primario) → yfinance (fallback)
Mercato: FMP API (primario) → yfinance (fallback)
"""

import warnings; warnings.filterwarnings('ignore')
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import json
import re
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Analisi Fondamentale Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Palette ───────────────────────────────────────────────────
BG      = "#0d1117"
AX_BG   = "#161b22"
CARD_BG = "#1c2128"
GRID_C  = "#21262d"
BORDER  = "#30363d"
TEXT_C  = "#e6edf3"
MUTED   = "#8b949e"
ACCENT  = "#58a6ff"
GREEN   = "#3fb950"
RED     = "#f78166"
ORANGE  = "#ffa657"
PURPLE  = "#d2a8ff"
COLORS  = [ACCENT, GREEN, RED, PURPLE, ORANGE,
           "#79c0ff", "#56d364", "#ff7b72"]

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:#0d1117;color:#e6edf3;}
[data-testid="stSidebar"]{background:#161b22;border-right:1px solid #21262d;}
[data-testid="stSidebar"] .stButton>button{width:100%;}
/* Cards */
.card{
  background:linear-gradient(135deg,#1c2128 0%,#161b22 100%);
  border:1px solid #30363d;border-radius:12px;
  padding:18px 14px;text-align:center;
  transition:all .2s ease;margin:3px;
  box-shadow:0 2px 8px rgba(0,0,0,.35);
}
.card:hover{border-color:#58a6ff;box-shadow:0 4px 18px rgba(88,166,255,.18);transform:translateY(-2px);}
.card-value{font-size:1.65rem;font-weight:700;letter-spacing:-.5px;line-height:1.2;}
.card-label{font-size:.72rem;color:#8b949e;margin-top:6px;text-transform:uppercase;letter-spacing:.5px;}
/* Section header */
.sh{display:flex;align-items:center;gap:8px;padding:10px 0 8px 0;
    border-bottom:1px solid #21262d;margin-bottom:14px;}
.sh-text{font-size:1.05rem;font-weight:600;color:#e6edf3;}
/* Verdict */
.v-buy{background:linear-gradient(135deg,#0d2018 0%,#1a3a2a 100%);
       border:2px solid #3fb950;border-radius:14px;padding:22px;
       box-shadow:0 4px 20px rgba(63,185,80,.2);}
.v-wait{background:linear-gradient(135deg,#1a1500 0%,#2a2200 100%);
        border:2px solid #ffa657;border-radius:14px;padding:22px;
        box-shadow:0 4px 20px rgba(255,166,87,.2);}
.v-avoid{background:linear-gradient(135deg,#200a0a 0%,#3a1010 100%);
         border:2px solid #f78166;border-radius:14px;padding:22px;
         box-shadow:0 4px 20px rgba(247,129,102,.2);}
.v-neutral{background:linear-gradient(135deg,#161b22 0%,#1c2128 100%);
           border:2px solid #8b949e;border-radius:14px;padding:22px;}
/* Score bar */
.sb-row{display:flex;align-items:center;gap:10px;margin:5px 0;}
.sb-label{width:180px;font-size:.84rem;color:#e6edf3;}
.sb-track{flex:1;background:#21262d;border-radius:5px;height:16px;overflow:hidden;}
.sb-fill{height:100%;border-radius:5px;opacity:.85;}
.sb-num{width:60px;font-weight:700;font-size:.88rem;}
.sb-w{font-size:.76rem;color:#8b949e;}
/* Flags */
.fcrit{background:#1e0a0a;border:1px solid #f78166;border-left:4px solid #f78166;
       border-radius:8px;padding:9px 13px;margin:3px 0;font-size:.88rem;}
.fwarn{background:#1a1400;border:1px solid #ffa657;border-left:4px solid #ffa657;
       border-radius:8px;padding:9px 13px;margin:3px 0;font-size:.88rem;}
/* Welcome feature cards */
.fc{background:#1c2128;border:1px solid #30363d;border-radius:12px;padding:18px;}
.fc-icon{font-size:1.8rem;margin-bottom:6px;}
.fc-title{font-weight:600;font-size:.95rem;margin-bottom:4px;}
.fc-desc{color:#8b949e;font-size:.82rem;}
/* Company header */
.co-header{background:linear-gradient(135deg,#1c2128 0%,#0d1117 100%);
           border:1px solid #30363d;border-radius:14px;padding:22px;margin-bottom:18px;}
/* Badge */
.badge{display:inline-block;background:#21262d;border:1px solid #30363d;
       border-radius:6px;padding:2px 8px;font-size:.73rem;color:#8b949e;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def fmt_m(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "N/A"
    b = v / 1e9
    if abs(b) >= 1: return f"${b:,.1f}B"
    return f"${v/1e6:,.1f}M"

def fmt_pct(v, dec=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "N/A"
    return f"{v*100:.{dec}f}%"

def fmt_x(v, dec=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "N/A"
    return f"{v:.{dec}f}x"

def last_valid(series):
    s = series.dropna() if hasattr(series,'dropna') else pd.Series(series).dropna()
    return float(s.iloc[-1]) if not s.empty else np.nan

def safe_div(n, d):
    try:
        if pd.isna(n) or pd.isna(d) or d == 0: return np.nan
        return n / d
    except: return np.nan

def cagr(series, n):
    s = series.dropna()
    if len(s) < 2: return np.nan
    yrs = s.index.max() - s.index.min()
    if yrs <= 0: return np.nan
    start, end = s.iloc[0], s.iloc[-1]
    if start <= 0 or end <= 0: return np.nan
    return (end / start) ** (1 / yrs) - 1

def score_clamped(v, thresholds):
    for thresh, sc in thresholds:
        if v <= thresh: return sc
    return thresholds[-1][1]

def card(label, value, color=None):
    c = color or ACCENT
    st.markdown(f"""
    <div class="card">
      <div class="card-value" style="color:{c}">{value}</div>
      <div class="card-label">{label}</div>
    </div>""", unsafe_allow_html=True)

def section(icon, title):
    st.markdown(f'<div class="sh"><span>{icon}</span>'
                f'<span class="sh-text">{title}</span></div>',
                unsafe_allow_html=True)

LAYOUT = dict(
    paper_bgcolor=BG, plot_bgcolor=AX_BG,
    font=dict(color=TEXT_C, family="Inter, sans-serif"),
    xaxis=dict(gridcolor=GRID_C, linecolor=GRID_C),
    yaxis=dict(gridcolor=GRID_C, linecolor=GRID_C),
    legend=dict(bgcolor=AX_BG, bordercolor=GRID_C),
    margin=dict(l=50, r=30, t=50, b=40),
)

def plo(fig, height=None):
    if height: fig.update_layout(height=height)
    fig.update_layout(**LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# SEC EDGAR
# ═══════════════════════════════════════════════════════════════
SEC_HDRS = {
    "User-Agent": "FundamentalAnalysisApp research@example.com",
    "Accept-Encoding": "gzip, deflate"
}

GAAP_TAGS = {
    "revenue":           ["RevenueFromContractWithCustomerExcludingAssessedTax",
                          "Revenues","SalesRevenueNet",
                          "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cost_of_revenue":   ["CostOfRevenue","CostOfGoodsAndServicesSold"],
    "gross_profit":      ["GrossProfit"],
    "operating_income":  ["OperatingIncomeLoss"],
    "net_income":        ["NetIncomeLoss","ProfitLoss"],
    "total_assets":      ["Assets"],
    "total_liabilities": ["Liabilities"],
    "total_equity":      ["StockholdersEquity",
                          "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "current_assets":    ["AssetsCurrent"],
    "current_liabilities":["LiabilitiesCurrent"],
    "long_term_debt":    ["LongTermDebt","LongTermDebtNoncurrent"],
    "short_term_debt":   ["ShortTermBorrowings","DebtCurrent","LongTermDebtCurrent"],
    "cash":              ["CashAndCashEquivalentsAtCarryingValue",
                          "CashCashEquivalentsAndShortTermInvestments"],
    "operating_cf":      ["NetCashProvidedByUsedInOperatingActivities"],
    "capex":             ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "interest_expense":  ["InterestExpense","InterestAndDebtExpense"],
    "income_tax":        ["IncomeTaxExpenseBenefit"],
    "depreciation":      ["DepreciationDepletionAndAmortization","Depreciation"],
    "inventory":         ["InventoryNet"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "shares_outstanding":["CommonStockSharesOutstanding",
                          "WeightedAverageNumberOfSharesOutstandingBasic"],
}

def get_cik(ticker):
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=SEC_HDRS, timeout=15)
    r.raise_for_status()
    for entry in r.json().values():
        if entry.get("ticker","").upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10), entry.get("title", ticker)
    raise ValueError(f"Ticker '{ticker}' non trovato in SEC EDGAR")

def fetch_companyfacts(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    r = requests.get(url, headers={**SEC_HDRS,"Host":"data.sec.gov"}, timeout=45)
    r.raise_for_status()
    return r.json()

def extract_series(facts_json, tag_list, unit="USD", annual=True):
    gaap = facts_json.get("facts",{}).get("us-gaap",{})
    for tag in tag_list:
        if tag not in gaap: continue
        raw = gaap[tag].get("units",{}).get(unit,[])
        if not raw: continue
        df = pd.DataFrame(raw)
        if df.empty or "val" not in df.columns: continue
        df["end"] = pd.to_datetime(df["end"], errors="coerce")
        df = df.dropna(subset=["end"])
        if annual:
            if "form" in df.columns:
                df = df[df["form"].isin(["10-K","20-F","10-K405"])].copy()
            if "start" in df.columns and not df.empty:
                df["start"] = pd.to_datetime(df["start"], errors="coerce")
                df["days"]  = (df["end"] - df["start"]).dt.days
                df = df[(df["days"]>=300)&(df["days"]<=400)]
        if df.empty: continue
        df["year"] = df["end"].dt.year
        df = df.sort_values("end").drop_duplicates("year", keep="last")
        return df.set_index("year")["val"].sort_index().astype(float)
    return pd.Series(dtype=float)

def _add_derived(df):
    if "gross_profit" not in df.columns and "revenue" in df.columns and "cost_of_revenue" in df.columns:
        df["gross_profit"] = df["revenue"] - df["cost_of_revenue"]
    lt = df.get("long_term_debt",  pd.Series(dtype=float)).reindex(df.index).fillna(0)
    st2= df.get("short_term_debt", pd.Series(dtype=float)).reindex(df.index).fillna(0)
    df["total_debt"] = lt + st2
    if "free_cash_flow" not in df.columns:
        if "operating_cf" in df.columns and "capex" in df.columns:
            df["free_cash_flow"] = df["operating_cf"] - df["capex"].abs()
        elif "operating_cf" in df.columns:
            df["free_cash_flow"] = df["operating_cf"]
    if "ebitda" not in df.columns and "operating_income" in df.columns and "depreciation" in df.columns:
        df["ebitda"] = df["operating_income"] + df["depreciation"].abs()
    if "working_capital" not in df.columns and "current_assets" in df.columns and "current_liabilities" in df.columns:
        df["working_capital"] = df["current_assets"] - df["current_liabilities"]
    return df

def build_sec_fundamentals(facts_json, years_back=10):
    series = {}
    for col, tags in GAAP_TAGS.items():
        unit = "shares" if col == "shares_outstanding" else "USD"
        s = extract_series(facts_json, tags, unit=unit)
        if not s.empty: series[col] = s
    if not series: return pd.DataFrame()
    df = pd.DataFrame(series)
    df = df[df.index >= datetime.now().year - years_back].copy()
    return _add_derived(df)

def build_yf_fundamentals(ticker_str, years_back=10):
    tk = yf.Ticker(ticker_str)
    inc, bal, cf = tk.financials, tk.balance_sheet, tk.cashflow

    def row(frame, *keys):
        if frame is None or frame.empty: return pd.Series(dtype=float)
        for k in keys:
            if k in frame.index:
                s = frame.loc[k].copy()
                s.index = pd.to_datetime(s.index).year
                return s.sort_index().astype(float)
        return pd.Series(dtype=float)

    series = {
        "revenue":            row(inc,"Total Revenue"),
        "gross_profit":       row(inc,"Gross Profit"),
        "operating_income":   row(inc,"Operating Income","EBIT"),
        "net_income":         row(inc,"Net Income"),
        "interest_expense":   row(inc,"Interest Expense"),
        "income_tax":         row(inc,"Tax Provision","Income Tax Expense"),
        "depreciation":       row(cf,"Depreciation And Amortization","Depreciation"),
        "total_assets":       row(bal,"Total Assets"),
        "total_liabilities":  row(bal,"Total Liabilities Net Minority Interest"),
        "total_equity":       row(bal,"Stockholders Equity","Total Stockholder Equity"),
        "current_assets":     row(bal,"Current Assets","Total Current Assets"),
        "current_liabilities":row(bal,"Current Liabilities","Total Current Liabilities"),
        "cash":               row(bal,"Cash And Cash Equivalents","Cash"),
        "long_term_debt":     row(bal,"Long Term Debt"),
        "short_term_debt":    row(bal,"Current Debt","Short Term Debt"),
        "operating_cf":       row(cf,"Operating Cash Flow","Cash From Operations"),
        "capex":              row(cf,"Capital Expenditure"),
        "shares_outstanding": row(bal,"Share Issued"),
    }
    df = pd.DataFrame({k:v for k,v in series.items() if not v.empty})
    if df.empty: raise ValueError("yfinance: dati non disponibili")
    df = df[df.index >= datetime.now().year - years_back].copy()
    if "operating_cf" in df.columns and "capex" in df.columns:
        df["free_cash_flow"] = df["operating_cf"] + df["capex"]
    return _add_derived(df)

@st.cache_data(ttl=900, show_spinner=False)
def get_market_data(ticker, fmp_key):
    result = {}
    if fmp_key:
        try:
            base = "https://financialmodelingprep.com/api/v3"
            prof = requests.get(f"{base}/profile/{ticker}",
                                params={"apikey":fmp_key}, timeout=12).json()
            if prof and isinstance(prof, list):
                p = prof[0]
                result.update({
                    "marketCap":p.get("mktCap"),"currentPrice":p.get("price"),
                    "sharesOutstanding":p.get("sharesOutstanding"),
                    "beta":p.get("beta",1.0),"sector":p.get("sector","N/A"),
                    "industry":p.get("industry","N/A"),"country":p.get("country","US"),
                    "shortName":p.get("companyName",ticker),
                    "totalDebt":p.get("totalDebt",0),
                    "totalCash":p.get("totalCash") or 0,
                    "description":p.get("description",""),
                    "image":p.get("image",""),
                    "website":p.get("website",""),
                })
            rat = requests.get(f"{base}/ratios-ttm/{ticker}",
                               params={"apikey":fmp_key}, timeout=12).json()
            if rat and isinstance(rat, list):
                r = rat[0]
                result.update({
                    "trailingPE":r.get("peRatioTTM"),
                    "priceToSalesTrailing12Months":r.get("priceToSalesRatioTTM"),
                    "priceToBookTTM":r.get("priceToBookRatioTTM"),
                    "evToEbitdaTTM":r.get("enterpriseValueMultipleTTM"),
                    "evToSalesTTM":r.get("evToSalesTTM"),
                    "netProfitMarginTTM":r.get("netProfitMarginTTM"),
                })
        except Exception: pass
    if not result.get("currentPrice"):
        try:
            info = yf.Ticker(ticker).info
            if info and len(info) > 5:
                result.setdefault("marketCap",        info.get("marketCap"))
                result.setdefault("currentPrice",     info.get("currentPrice") or info.get("regularMarketPrice"))
                result.setdefault("sharesOutstanding",info.get("sharesOutstanding"))
                result.setdefault("beta",             info.get("beta",1.0))
                result.setdefault("sector",           info.get("sector","N/A"))
                result.setdefault("industry",         info.get("industry","N/A"))
                result.setdefault("shortName",        info.get("shortName",ticker))
                result.setdefault("trailingPE",       info.get("trailingPE"))
                result.setdefault("priceToSalesTrailing12Months",
                                  info.get("priceToSalesTrailing12Months"))
                result.setdefault("description",      info.get("longBusinessSummary",""))
        except Exception: pass
    return result

@st.cache_data(ttl=900, show_spinner=False)
def load_fundamentals(ticker, years_back):
    try:
        cik, name = get_cik(ticker)
        time.sleep(0.3)
        facts = fetch_companyfacts(cik)
        df = build_sec_fundamentals(facts, years_back)
        if df.empty: raise ValueError("DataFrame vuoto")
        return df, name, "SEC EDGAR XBRL"
    except Exception as e_sec:
        try:
            return build_yf_fundamentals(ticker, years_back), ticker, "yfinance (fallback)"
        except Exception as e_yf:
            raise RuntimeError(f"SEC={e_sec} | yf={e_yf}")

@st.cache_data(ttl=600, show_spinner=False)
def get_peer_data(peer_tickers, fmp_key):
    """Fetch peer fundamentals — yfinance primary, FMP optional enrichment."""
    rows = []
    for t in peer_tickers:
        try:
            info = yf.Ticker(t).info
            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                raise ValueError("no info")
            px   = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            mcap = info.get("marketCap")
            pe   = info.get("trailingPE")   or info.get("forwardPE")
            pb   = info.get("priceToBook")
            ps   = info.get("priceToSalesTrailing12Months")
            evebitda = info.get("enterpriseToEbitda")
            evsales  = info.get("enterpriseToRevenue")
            nm   = info.get("profitMargins")
            name = (info.get("shortName") or info.get("longName") or t)[:22]
            sect = info.get("sector","N/A")
            # --- NEW: EV/FCF and Dividend Yield ---
            ev_raw  = info.get("enterpriseValue")
            fcf_raw = info.get("freeCashflow")
            ev_fcf  = None
            if ev_raw and fcf_raw and fcf_raw != 0:
                _ev_fcf_v = float(ev_raw) / float(fcf_raw)
                ev_fcf = _ev_fcf_v if 0 < _ev_fcf_v < 500 else None
            div_yield = info.get("dividendYield")
            rows.append({
                "Ticker":t,"Nome":name,
                "Market Cap":mcap,"Prezzo":px,
                "P/E":pe,"P/B":pb,"P/S":ps,
                "EV/EBITDA":evebitda,"EV/Sales":evsales,
                "EV/FCF":ev_fcf,"Div Yield":div_yield,
                "Net Margin":nm,"Settore":sect,
            })
        except Exception:
            # FMP fallback for this ticker
            if fmp_key:
                try:
                    base = "https://financialmodelingprep.com/api/v3"
                    time.sleep(0.2)
                    prof = requests.get(f"{base}/profile/{t}",  params={"apikey":fmp_key}, timeout=8).json()
                    rat  = requests.get(f"{base}/ratios-ttm/{t}",params={"apikey":fmp_key}, timeout=8).json()
                    if not prof or not isinstance(prof, list): continue
                    p = prof[0]; r = rat[0] if rat and isinstance(rat,list) else {}
                    # EV/FCF from FMP ratios
                    _ev_fmp   = p.get("enterpriseValue") or p.get("mktCap")
                    _fcf_fmp  = r.get("freeCashFlowPerShareTTM")
                    _shs_fmp  = p.get("sharesOutstanding") or 1
                    _ev_fcf_f = None
                    if _ev_fmp and _fcf_fmp and _shs_fmp:
                        try:
                            _fcf_tot = float(_fcf_fmp) * float(_shs_fmp)
                            if _fcf_tot != 0:
                                _v_ef = float(_ev_fmp) / _fcf_tot
                                _ev_fcf_f = _v_ef if 0 < _v_ef < 500 else None
                        except Exception:
                            pass
                    rows.append({
                        "Ticker":t,"Nome":(p.get("companyName",""))[:22],
                        "Market Cap":p.get("mktCap"),"Prezzo":p.get("price"),
                        "P/E":r.get("peRatioTTM"),"P/B":r.get("priceToBookRatioTTM"),
                        "P/S":r.get("priceToSalesRatioTTM"),
                        "EV/EBITDA":r.get("enterpriseValueMultipleTTM"),
                        "EV/Sales":r.get("evToSalesTTM"),
                        "EV/FCF":_ev_fcf_f,
                        "Div Yield":r.get("dividendYieldTTM"),
                        "Net Margin":r.get("netProfitMarginTTM"),
                        "Settore":p.get("sector","N/A"),
                    })
                except Exception: continue
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("Ticker")
    for col in ["P/E","P/B","P/S","EV/EBITDA","EV/Sales","EV/FCF"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].where((df[col]>0)&(df[col]<1000))
    if "Net Margin" in df.columns:
        df["Net Margin"] = pd.to_numeric(df["Net Margin"], errors="coerce")  # keep as 0..1 for fmt_pct
    if "Div Yield" in df.columns:
        df["Div Yield"] = pd.to_numeric(df["Div Yield"], errors="coerce")
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def get_fred_series(series_id, api_key, start="2014-01-01"):
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={api_key}&file_type=json"
           f"&observation_start={start}&sort_order=asc")
    r = requests.get(url, timeout=15)
    data = r.json().get("observations",[])
    df = pd.DataFrame(data)
    df = df[df["value"]!="."]
    df["value"] = df["value"].astype(float)
    df["date"]  = pd.to_datetime(df["date"])
    return df.set_index("date")["value"]

@st.cache_data(ttl=600, show_spinner=False)
def get_news_sentiment(ticker, company_name, news_key):
    headlines = []; source = "N/A"
    if news_key:
        try:
            resp = requests.get("https://newsapi.org/v2/everything",
                params={"q":ticker,"language":"en","pageSize":30,
                        "sortBy":"publishedAt","apiKey":news_key},timeout=15).json()
            if resp.get("status")=="ok":
                headlines=[a.get("title","") for a in resp.get("articles",[])
                           if a.get("title") and "[Removed]" not in a.get("title","")]
                source="NewsAPI"
        except Exception: pass
    if not headlines:
        try:
            av = requests.get("https://www.alphavantage.co/query",
                params={"function":"NEWS_SENTIMENT","tickers":ticker,
                        "limit":30,"apikey":"demo"},timeout=15).json()
            feed = av.get("feed",[])
            if feed:
                headlines=[a.get("title","") for a in feed if a.get("title")]
                source="Alpha Vantage"
        except Exception: pass
    if not headlines:
        try:
            import xml.etree.ElementTree as ET
            rss = requests.get(
                f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
                headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            if rss.status_code==200:
                root=ET.fromstring(rss.content)
                headlines=[it.findtext("title","") for it in root.findall(".//item") if it.findtext("title")]
                source="Yahoo RSS"
        except Exception: pass
    if not headlines:
        return {"scores":[],"labels":[],"avg":0,"source":"N/A",
                "headlines":[],"model":"N/A","pos_pct":0,"neg_pct":0,"neu_pct":0}
    scores, labels, model_used = [], [], "N/A"
    try:
        from transformers import pipeline as hfp
        pipe = hfp("sentiment-analysis", model="ProsusAI/finbert",
                   truncation=True, max_length=512, device=-1)
        lmap = {"positive":1,"negative":-1,"neutral":0}
        for h in headlines:
            res=pipe(h[:512])[0]
            scores.append(lmap.get(res["label"].lower(),0))
            labels.append(res["label"].lower())
        model_used="FinBERT"
    except Exception:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as VSA
            vader=VSA()
            for h in headlines:
                c=vader.polarity_scores(h)["compound"]
                scores.append(c)
                labels.append("positive" if c>=.05 else "negative" if c<=-.05 else "neutral")
            model_used="VADER"
        except Exception: pass
    if not scores:
        return {"scores":[],"labels":[],"avg":0,"source":source,
                "headlines":headlines,"model":"N/A","pos_pct":0,"neg_pct":0,"neu_pct":0}
    n=len(labels)
    return {"scores":scores,"labels":labels,"avg":float(np.mean(scores)),
            "source":source,"headlines":headlines,"model":model_used,
            "pos_pct":sum(1 for l in labels if l=="positive")/n*100,
            "neg_pct":sum(1 for l in labels if l=="negative")/n*100,
            "neu_pct":sum(1 for l in labels if l=="neutral")/n*100}

@st.cache_data(ttl=900, show_spinner=False)
def get_price_history_daily(ticker, benchmark="SPY", period="2y"):
    try:
        px = yf.download([ticker, benchmark], period=period, interval="1d",
                         auto_adjust=True, progress=False)["Close"]
        if isinstance(px, pd.Series): px = px.to_frame(ticker)
        return px.dropna(how="all")
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def get_price_history_weekly(ticker, benchmark="SPY", period="5y"):
    try:
        px = yf.download([ticker, benchmark], period=period, interval="1wk",
                         auto_adjust=True, progress=False)["Close"]
        if isinstance(px, pd.Series): px = px.to_frame(ticker)
        return px.dropna(how="all")
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def get_forward_data(ticker):
    result = {}
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        for k in ["forwardPE","forwardEps","trailingEps","earningsGrowth",
                  "revenueGrowth","trailingPE","recommendationKey","targetMeanPrice",
                  "targetLowPrice","targetHighPrice","targetMedianPrice",
                  "numberOfAnalystOpinions"]:
            result[k] = info.get(k)
        try:
            rec = tk.recommendations_summary
            if rec is not None and not rec.empty:
                result["rec_df"] = rec.to_dict("records")
        except Exception: pass
        try:
            eps_est = tk.eps_estimate
            if eps_est is not None and not eps_est.empty:
                result["eps_estimate"] = eps_est.to_dict()
        except Exception: pass
    except Exception: pass
    return result

# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
# ── API Keys — costanti nascoste (non esposte in UI) ──────────────────────
fmp_key  = "gxSzdX9p7VNJgDllMKwaGYJiOLP7G2ZE"
fred_key = "a9417b702a6284348b7e82025932fc80"
news_key = "0cded333d500476abd8e72904ca746ba"

# ── Session state: ricorda che l'analisi è stata avviata ─────────────────
if "analysis_ran" not in st.session_state:
    st.session_state["analysis_ran"] = False
if "last_ticker" not in st.session_state:
    st.session_state["last_ticker"] = ""

with st.sidebar:
    st.markdown("## ⚙️ Configurazione")
    st.markdown("---")
    ticker = st.text_input("**Ticker**", value="AAPL",
                           help="Es: AAPL, MSFT, NVDA, PLTR, TSLA").upper().strip()
    years_back = st.slider("**Anni di storia**", 3, 15, 10)

    st.markdown("---")
    peer_input = st.text_input("**Peer Tickers** (virgola)",
                                placeholder="MSFT,GOOGL,META")
    st.markdown("---")
    run_btn = st.button("🚀 **AVVIA ANALISI**", use_container_width=True, type="primary")
    if run_btn:
        st.session_state["analysis_ran"] = True
        st.session_state["last_ticker"]  = ticker

    st.markdown("---")
    st.markdown(f"""
    <div style="font-size:.75rem;color:{MUTED};text-align:center">
    📊 Analisi Fondamentale v4<br>
    SEC EDGAR · FMP · FRED · NewsAPI<br>
    WACC calcolato automaticamente<br>
    (Beta OLS Blume + Damodaran ERP)<br><br>
    ⚠️ Solo uso educativo/informativo.<br>
    Non è consulenza finanziaria.
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# WELCOME SCREEN
# ═══════════════════════════════════════════════════════════════
_show_analysis = run_btn or st.session_state.get("analysis_ran", False)

if not _show_analysis:
    st.markdown("""
    <div style="text-align:center;padding:40px 0 20px 0;">
      <div style="font-size:3rem;">📊</div>
      <h1 style="font-size:2.2rem;font-weight:700;margin:8px 0;">Analisi Fondamentale Pro</h1>
      <p style="color:#8b949e;font-size:1.05rem;max-width:600px;margin:0 auto;">
        Dashboard professionale per l'analisi fondamentale di azioni quotate.
        Dati real-time da SEC EDGAR, FMP, FRED e NewsAPI.
      </p>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    feats = [
        ("📈","Margini & Profittabilità","Gross, Operating e Net Margin storici con trend e scoring euristico."),
        ("🎯","ROIC vs WACC","Analisi creazione di valore: spread economico e confronto con costo del capitale."),
        ("🔮","DCF & Fair Value","Modello DCF multi-scenario con sensitivity analysis e margine di sicurezza."),
        ("🏆","Analisi Competitor","Confronto multipli vs peer di settore con radar chart interattivo."),
    ]
    for col,(icon,title,desc) in zip([c1,c2,c3,c4],feats):
        with col:
            st.markdown(f"""<div class="fc">
              <div class="fc-icon">{icon}</div>
              <div class="fc-title">{title}</div>
              <div class="fc-desc">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    cl,cr = st.columns([1,1])
    with cl:
        st.markdown("### 📋 Come si usa")
        st.markdown("""
1. Inserisci il **ticker** nella sidebar (es. `AAPL`, `MSFT`, `NVDA`)
2. Regola gli **anni di storia**
3. Le API key sono già precompilate (gratuiti)
4. Premi **🚀 AVVIA ANALISI**
5. Naviga le **8 tab** della dashboard
        """)
    with cr:
        st.markdown("### 🌐 Fonti dati")
        st.markdown("""
| Fonte | Contenuto | Piano |
|-------|-----------|-------|
| SEC EDGAR | Bilanci ufficiali XBRL | Gratuito |
| FMP API | Prezzi, multipli, peer | Gratuito |
| FRED | PIL, inflazione, tassi | Gratuito |
| NewsAPI | News finanziarie | Gratuito |
        """)
    st.stop()

# ═══════════════════════════════════════════════════════════════
# CARICAMENTO DATI
# ═══════════════════════════════════════════════════════════════
with st.spinner(f"📡 Carico fondamentali per **{ticker}**…"):
    try:
        df_fund, company_name, data_source = load_fundamentals(ticker, years_back)
    except Exception as e:
        st.error(f"❌ Impossibile caricare dati per **{ticker}**: {e}")
        st.stop()

with st.spinner("📡 Carico dati di mercato…"):
    mkt        = get_market_data(ticker, fmp_key)
    market_cap = mkt.get("marketCap")
    price      = mkt.get("currentPrice")
    shares     = mkt.get("sharesOutstanding")
    sector     = mkt.get("sector","N/A")
    industry   = mkt.get("industry","N/A")
    beta       = mkt.get("beta",1.0)
    description= mkt.get("description","")
    logo_url   = mkt.get("image","")

# ═══════════════════════════════════════════════════════════════
# CALCOLI FONDAMENTALI (eseguiti tutti prima dell'UI)
# ═══════════════════════════════════════════════════════════════

# Net debt & EV
nd_last = None
if "total_debt" in df_fund.columns and "cash" in df_fund.columns:
    nd_last = (last_valid(df_fund["total_debt"]) or 0) - (last_valid(df_fund["cash"]) or 0)
ev = (market_cap + nd_last) if market_cap and nd_last is not None else market_cap

# --- Margini ---
margins = {}
if "gross_profit"    in df_fund.columns and "revenue" in df_fund.columns:
    margins["Gross Margin"]     = df_fund["gross_profit"]    / df_fund["revenue"]
if "operating_income" in df_fund.columns and "revenue" in df_fund.columns:
    margins["Operating Margin"] = df_fund["operating_income"]/ df_fund["revenue"]
if "net_income"       in df_fund.columns and "revenue" in df_fund.columns:
    margins["Net Margin"]       = df_fund["net_income"]      / df_fund["revenue"]
if "ebitda"           in df_fund.columns and "revenue" in df_fund.columns:
    margins["EBITDA Margin"]    = df_fund["ebitda"]          / df_fund["revenue"]

# score profittabilità
score_prof = np.nan
nm_v = last_valid(margins.get("Net Margin",     pd.Series()))
om_v = last_valid(margins.get("Operating Margin",pd.Series()))
scores_m = []
for v in [nm_v, om_v]:
    if not pd.isna(v):
        scores_m.append(score_clamped(v,[(-0.05,5),(0,20),(0.05,40),(0.10,60),(0.15,75),(0.25,90),(1,100)]))
if scores_m: score_prof = float(np.mean(scores_m))

# --- ROA / ROE ---
roa = pd.Series(dtype=float)
roe = pd.Series(dtype=float)
if "net_income" in df_fund.columns and "total_assets" in df_fund.columns:
    roa = df_fund["net_income"] / df_fund["total_assets"]
if "net_income" in df_fund.columns and "total_equity" in df_fund.columns:
    roe = df_fund["net_income"] / df_fund["total_equity"]

# --- ROIC ---
roic = pd.Series(dtype=float)
nopat = inv_cap = pd.Series(dtype=float)
need_roic = ["operating_income","total_debt","total_equity","cash"]
if all(c in df_fund.columns for c in need_roic):
    if "income_tax" in df_fund.columns:
        pre_tax  = df_fund["operating_income"].clip(lower=1)
        raw_rate = (df_fund["income_tax"]/pre_tax).clip(0,0.40)
        tax_rate = raw_rate.where(raw_rate>0, 0.21)
    else:
        tax_rate = pd.Series(0.21, index=df_fund.index)
    nopat   = df_fund["operating_income"] * (1 - tax_rate)
    inv_cap = df_fund["total_debt"] + df_fund["total_equity"] - df_fund["cash"].fillna(0)
    min_ic  = (df_fund["total_assets"].abs()*0.05 if "total_assets" in df_fund.columns
               else pd.Series(1e8, index=df_fund.index))
    roic_raw = nopat / inv_cap.replace(0, np.nan)
    roic     = roic_raw.where((inv_cap.abs()>=min_ic)&(inv_cap>0), np.nan)

# --- Liquidità & Solvibilità ---
liq = {}
if "current_assets" in df_fund.columns and "current_liabilities" in df_fund.columns:
    liq["Current Ratio"]   = df_fund["current_assets"] / df_fund["current_liabilities"].replace(0,np.nan)
if "total_debt" in df_fund.columns and "total_equity" in df_fund.columns:
    liq["D/E Ratio"]       = df_fund["total_debt"] / df_fund["total_equity"].replace(0,np.nan)
if "total_debt" in df_fund.columns and "cash" in df_fund.columns and "ebitda" in df_fund.columns:
    nd_s = df_fund["total_debt"] - df_fund["cash"].fillna(0)
    liq["Net Debt/EBITDA"] = nd_s / df_fund["ebitda"].replace(0,np.nan)
if "operating_income" in df_fund.columns and "interest_expense" in df_fund.columns:
    liq["Interest Coverage"]= df_fund["operating_income"] / df_fund["interest_expense"].abs().replace(0,np.nan)

cr_v  = last_valid(liq.get("Current Ratio", pd.Series()))
de_v  = last_valid(liq.get("D/E Ratio",     pd.Series()))
scores_s = []
if not pd.isna(cr_v): scores_s.append(score_clamped(cr_v,[(0.5,10),(1,40),(1.5,65),(2,80),(3,90),(10,100)]))
if not pd.isna(de_v): scores_s.append(score_clamped(de_v,[(0,95),(0.5,85),(1,75),(2,60),(3,40),(5,20),(99,5)]))
score_solv = float(np.mean(scores_s)) if scores_s else np.nan

# --- Cash Flow ---
cf_metrics = {}
if "operating_cf" in df_fund.columns and "net_income" in df_fund.columns:
    cf_metrics["CFO/Net Income"] = df_fund["operating_cf"] / df_fund["net_income"].replace(0,np.nan)
if "free_cash_flow" in df_fund.columns and "revenue" in df_fund.columns:
    cf_metrics["FCF Margin"]     = df_fund["free_cash_flow"] / df_fund["revenue"].replace(0,np.nan)
if "capex" in df_fund.columns and "revenue" in df_fund.columns:
    cf_metrics["CapEx Intensity"]= df_fund["capex"].abs() / df_fund["revenue"].replace(0,np.nan)

fcf_last = last_valid(cf_metrics.get("FCF Margin",      pd.Series()))
cfo_ni   = last_valid(cf_metrics.get("CFO/Net Income",  pd.Series()))
scores_c = []
if not pd.isna(fcf_last): scores_c.append(score_clamped(fcf_last,[(-0.1,10),(0,30),(0.05,50),(0.1,65),(0.15,80),(0.25,95),(1,100)]))
if not pd.isna(cfo_ni) and cfo_ni>0: scores_c.append(score_clamped(cfo_ni,[(0.3,20),(0.6,40),(0.8,55),(1.0,70),(1.5,85),(3,100)]))
score_cf = float(np.mean(scores_c)) if scores_c else np.nan

# --- Crescita ---
growth = {}
for col_name, label in [("revenue","Revenue"),("net_income","Net Income"),
                         ("free_cash_flow","FCF"),("ebitda","EBITDA")]:
    if col_name not in df_fund.columns: continue
    s = df_fund[col_name].dropna()
    if len(s) < 2: continue
    for n in [3,5,7]:
        s_n = s[s.index >= s.index.max()-n]
        if len(s_n) >= 2:
            growth[f"{label} CAGR {n}y"] = cagr(s_n, n)

rev_cagr_5y = growth.get("Revenue CAGR 5y", growth.get("Revenue CAGR 3y", np.nan))
fcf_cagr_5y = growth.get("FCF CAGR 5y",     growth.get("FCF CAGR 3y",     np.nan))
scores_g = []
for v in [rev_cagr_5y, fcf_cagr_5y]:
    if not pd.isna(v):
        scores_g.append(score_clamped(v,[(-0.1,5),(0,20),(0.05,40),(0.1,60),(0.15,75),(0.25,90),(1,100)]))
score_gr = float(np.mean(scores_g)) if scores_g else np.nan

# --- Valuation multipli ---
valuation = {}
if market_cap and market_cap > 0:
    ni_last    = last_valid(df_fund.get("net_income",   pd.Series()))
    rev_last   = last_valid(df_fund.get("revenue",      pd.Series()))
    ebitda_last= last_valid(df_fund.get("ebitda",       pd.Series()))
    eq_last    = last_valid(df_fund.get("total_equity",  pd.Series()))
    ev_v       = market_cap + (nd_last or 0)
    if ni_last and ni_last>0: valuation["P/E"] = market_cap/ni_last
    elif mkt.get("trailingPE"): valuation["P/E"] = mkt["trailingPE"]
    if rev_last and rev_last>0: valuation["P/S"] = market_cap/rev_last
    elif mkt.get("priceToSalesTrailing12Months"): valuation["P/S"] = mkt["priceToSalesTrailing12Months"]
    if ebitda_last and ebitda_last>0: valuation["EV/EBITDA"] = ev_v/ebitda_last
    elif mkt.get("evToEbitdaTTM"): valuation["EV/EBITDA"] = mkt["evToEbitdaTTM"]
    if rev_last and rev_last>0: valuation["EV/Revenue"] = ev_v/rev_last
    if eq_last and eq_last>0: valuation["P/B"] = market_cap/eq_last
    elif mkt.get("priceToBookTTM"): valuation["P/B"] = mkt["priceToBookTTM"]
    rev_cagr3 = growth.get("Revenue CAGR 3y")
    if "P/E" in valuation and rev_cagr3 and rev_cagr3>0:
        valuation["PEG"] = valuation["P/E"]/(rev_cagr3*100)

# ═══════════════════════════════════════════════════════════════
# NUOVI CALCOLI — Beta/WACC · DuPont · Risk · Multi-Model · Scenario
# ═══════════════════════════════════════════════════════════════

# ── Carica storici prezzi (necessari per beta, risk) ──────────────────────
with st.spinner("📡 Carico storico prezzi…"):
    px_weekly = get_price_history_weekly(ticker)
    px_daily  = get_price_history_daily(ticker)
    fwd_data  = get_forward_data(ticker)

# ── Beta OLS + Blume + WACC ───────────────────────────────────────────────
beta_ols  = float(beta or 1.0)
r_sq_ols  = 0.0
n_obs_ols = 0
beta_ret_x = np.array([])  # for scatter plot
beta_ret_y = np.array([])
rf_rate   = 0.043
erp       = 0.045

if not px_weekly.empty and ticker in px_weekly.columns and "SPY" in px_weekly.columns:
    try:
        from scipy import stats as _sp_stats
        ret_s = px_weekly[ticker].pct_change().dropna()
        ret_b = px_weekly["SPY"].pct_change().dropna()
        common_idx = ret_s.index.intersection(ret_b.index)
        if len(common_idx) > 20:
            xv = ret_b.reindex(common_idx).values
            yv = ret_s.reindex(common_idx).values
            mask = ~(np.isnan(xv) | np.isnan(yv))
            xv, yv = xv[mask], yv[mask]
            if len(xv) > 10:
                sl, ic, rv, pv, se = _sp_stats.linregress(xv, yv)
                beta_ols  = float(sl)
                r_sq_ols  = float(rv**2)
                n_obs_ols = len(xv)
                beta_ret_x = xv * 100
                beta_ret_y = yv * 100
    except Exception: pass

beta_blume = 2/3 * beta_ols + 1/3
mktcap_b   = (market_cap or 1e11) / 1e9
size_prem  = 0.0 if mktcap_b >= 10 else (0.005 if mktcap_b >= 2 else (0.010 if mktcap_b >= 0.3 else 0.015))
ke_calc    = rf_rate + beta_blume * erp + size_prem

int_exp_last = last_valid(df_fund.get("interest_expense", pd.Series()))
debt_last2   = last_valid(df_fund.get("total_debt", pd.Series()))
tax_rate_w   = 0.21
if "income_tax" in df_fund.columns and "operating_income" in df_fund.columns:
    _oi_w = df_fund["operating_income"].clip(lower=1)
    _tr_w = (df_fund["income_tax"] / _oi_w).clip(0, 0.40).dropna()
    if not _tr_w.empty: tax_rate_w = float(_tr_w.iloc[-1])
kd_pretax  = safe_div(abs(int_exp_last or 0), debt_last2 or 1) if (debt_last2 and debt_last2 > 0) else 0.05
kd_pretax  = max(0.01, min(0.15, kd_pretax))
kd_calc    = kd_pretax * (1 - tax_rate_w)
eq_w_wacc  = (market_cap / (market_cap + (debt_last2 or 0))) if market_cap and market_cap > 0 else 0.8
debt_w_wacc= 1 - eq_w_wacc
wacc_calc  = ke_calc * eq_w_wacc + kd_calc * debt_w_wacc
wacc_calc  = max(0.05, min(0.25, wacc_calc))

# Rolling Beta (60-day window)
rolling_beta = pd.Series(dtype=float)
if not px_daily.empty and ticker in px_daily.columns and "SPY" in px_daily.columns:
    try:
        _rta = px_daily[ticker].pct_change().dropna()
        _rsa = px_daily["SPY"].pct_change().dropna()
        _aln = _rta.align(_rsa, join="inner")
        rolling_beta = _aln[0].rolling(60).cov(_aln[1]) / _aln[1].rolling(60).var()
    except Exception: pass

# ── DuPont 5-Factor ───────────────────────────────────────────────────────
dupont5 = {}
_ni_d  = df_fund.get("net_income",       pd.Series(dtype=float))
_rev_d = df_fund.get("revenue",          pd.Series(dtype=float))
_ta_d  = df_fund.get("total_assets",     pd.Series(dtype=float))
_eq_d  = df_fund.get("total_equity",     pd.Series(dtype=float))
_ebit_d= df_fund.get("operating_income", pd.Series(dtype=float))
if "income_tax" in df_fund.columns:
    _ebt_d = (_ni_d.add(df_fund["income_tax"].abs(), fill_value=0))
else:
    _ebt_d = _ni_d / max(1 - tax_rate_w, 0.01)
_idx5 = (_ni_d.dropna().index.intersection(_rev_d.dropna().index)
         .intersection(_ta_d.dropna().index).intersection(_eq_d.dropna().index)
         .intersection(_ebit_d.dropna().index).intersection(_ebt_d.dropna().index))
if len(_idx5) > 0:
    _eq5   = _eq_d.reindex(_idx5).replace(0, np.nan)
    _ebt5  = _ebt_d.reindex(_idx5).replace(0, np.nan)
    _ebit5 = _ebit_d.reindex(_idx5).replace(0, np.nan)
    _rev5  = _rev_d.reindex(_idx5).replace(0, np.nan)
    _ni5   = _ni_d.reindex(_idx5)
    _ta5   = _ta_d.reindex(_idx5)
    dupont5["Tax Burden"]     = _ni5 / _ebt5
    dupont5["Interest Burden"]= _ebt5 / _ebit5
    dupont5["EBIT Margin"]    = _ebit5 / _rev5
    dupont5["Asset Turnover"] = _rev5 / _ta5
    dupont5["Leverage"]       = _ta5 / _eq5.replace(0, np.nan)
    dupont5["ROE (5-step)"]   = (dupont5["Tax Burden"] * dupont5["Interest Burden"] *
                                  dupont5["EBIT Margin"] * dupont5["Asset Turnover"] *
                                  dupont5["Leverage"])

# ── Activity Ratios ───────────────────────────────────────────────────────
activity = {}
_inv_a  = df_fund.get("inventory",       pd.Series(dtype=float))
_cogs_a = df_fund.get("cost_of_revenue", pd.Series(dtype=float))
_rev_a2 = df_fund.get("revenue",         pd.Series(dtype=float))
_ta_a2  = df_fund.get("total_assets",    pd.Series(dtype=float))
if not _inv_a.dropna().empty and not _cogs_a.dropna().empty:
    _avg_inv = ((_inv_a + _inv_a.shift(1)) / 2).where(lambda s: s > 0)
    _idx_inv = _cogs_a.dropna().index.intersection(_avg_inv.dropna().index)
    if not _idx_inv.empty:
        _inv_t = _cogs_a.reindex(_idx_inv) / _avg_inv.reindex(_idx_inv)
        activity["Inv Turnover"] = _inv_t
        activity["DIO (days)"]   = 365 / _inv_t
if not _rev_a2.dropna().empty and not _ta_a2.dropna().empty:
    _idx_at2 = _rev_a2.dropna().index.intersection(_ta_a2[_ta_a2 > 0].dropna().index)
    if not _idx_at2.empty:
        activity["Asset Turnover"] = _rev_a2.reindex(_idx_at2) / _ta_a2.reindex(_idx_at2)

# ── Risk Metrics ──────────────────────────────────────────────────────────
risk_metrics = {}
dd_series   = pd.Series(dtype=float)
px_tk_daily = pd.Series(dtype=float)
ret_tk_daily= pd.Series(dtype=float)
risk_class  = "N/A"
ann_vol_r   = np.nan; max_dd_r = np.nan; sharpe_r = np.nan
var_95_r    = np.nan; cvar_95_r= np.nan; sortino_r= np.nan

if not px_daily.empty and ticker in px_daily.columns:
    try:
        px_tk_daily  = px_daily[ticker].dropna()
        ret_tk_daily = px_tk_daily.pct_change().dropna()
        if len(ret_tk_daily) > 30:
            ann_ret_r  = float((1 + ret_tk_daily.mean()) ** 252 - 1)
            ann_vol_r  = float(ret_tk_daily.std() * np.sqrt(252))
            _dret      = ret_tk_daily[ret_tk_daily < 0]
            _dv        = float(_dret.std() * np.sqrt(252)) if len(_dret) > 0 else np.nan
            sharpe_r   = (ann_ret_r - rf_rate) / ann_vol_r if ann_vol_r > 0 else np.nan
            sortino_r  = ann_ret_r / _dv if (not np.isnan(_dv) and _dv > 0) else np.nan
            _roll_max  = px_tk_daily.cummax()
            dd_series  = (px_tk_daily - _roll_max) / _roll_max
            max_dd_r   = float(dd_series.min())
            var_95_r   = float(np.percentile(ret_tk_daily, 5))
            _cv        = ret_tk_daily[ret_tk_daily <= var_95_r]
            cvar_95_r  = float(_cv.mean()) if len(_cv) > 0 else np.nan
            _52w       = px_tk_daily.tail(252)
            dist_52h   = (float(px_tk_daily.iloc[-1]) - float(_52w.max())) / float(_52w.max())
            dist_52l   = (float(px_tk_daily.iloc[-1]) - float(_52w.min())) / float(_52w.min())
            calmar_r   = ann_ret_r / abs(max_dd_r) if max_dd_r < 0 else np.nan
            risk_metrics = {
                "Ann. Return":     ann_ret_r, "Ann. Volatility": ann_vol_r,
                "Sharpe Ratio":    sharpe_r,  "Sortino Ratio":   sortino_r,
                "Calmar Ratio":    calmar_r,  "Max Drawdown":    max_dd_r,
                "VaR 95% (1d)":   var_95_r,  "CVaR 95% (1d)":  cvar_95_r,
                "Dist 52W High":  dist_52h,  "Dist 52W Low":    dist_52l,
            }
            risk_class = ("HIGH" if (ann_vol_r > 0.35 or max_dd_r < -0.40)
                         else "MEDIUM" if (ann_vol_r > 0.20 or max_dd_r < -0.25)
                         else "LOW")
    except Exception: pass

# ── Quality of Earnings ───────────────────────────────────────────────────
df_quality = pd.DataFrame()
try:
    _qoe_rows = []
    _ni_s2  = df_fund.get("net_income",  pd.Series(dtype=float)).dropna()
    _cfo_s2 = df_fund.get("operating_cf",pd.Series(dtype=float)).dropna()
    _fcf_s2 = df_fund.get("free_cash_flow",pd.Series(dtype=float)).dropna()
    _rev_s2 = df_fund.get("revenue",     pd.Series(dtype=float)).dropna()
    _ta_s2  = df_fund.get("total_assets",pd.Series(dtype=float)).dropna()
    for _yr in sorted(_ni_s2.index)[-8:]:
        _ni_v  = _ni_s2.get(_yr, np.nan)
        _cfo_v = _cfo_s2.get(_yr, np.nan)
        _fcf_v = _fcf_s2.get(_yr, np.nan)
        _rev_v = _rev_s2.get(_yr, np.nan)
        _ta_v  = _ta_s2.get(_yr, np.nan)
        _cfo_ni = safe_div(_cfo_v, _ni_v)
        _fcf_ni = safe_div(_fcf_v, _ni_v)
        _acc    = safe_div((_ni_v or np.nan) - (_cfo_v or np.nan),
                           (_ta_v or np.nan)) if not np.isnan(_ta_v or np.nan) else np.nan
        _qoe_rows.append({
            "Anno": _yr,
            "NI ($M)":  int(round(_ni_v/1e6, 0)) if not np.isnan(_ni_v) else np.nan,
            "CFO ($M)": int(round(_cfo_v/1e6,0)) if not np.isnan(_cfo_v) else np.nan,
            "FCF ($M)": int(round(_fcf_v/1e6,0)) if not np.isnan(_fcf_v) else np.nan,
            "CFO/NI":   round(_cfo_ni, 2) if not np.isnan(_cfo_ni) else np.nan,
            "FCF/NI":   round(_fcf_ni, 2) if not np.isnan(_fcf_ni) else np.nan,
            "Accruals": round(_acc, 4) if not np.isnan(_acc) else np.nan,
        })
    df_quality = pd.DataFrame(_qoe_rows).set_index("Anno")
except Exception: pass

# ── Scenario Analysis (Bear/Base/Bull) ────────────────────────────────────
scenario_results = {}
_rev_base_sc = last_valid(df_fund.get("revenue", pd.Series()))
_wacc_sc     = wacc_calc
_tgr_sc      = 0.025
_shares_sc   = last_valid(df_fund.get("shares_outstanding", pd.Series())) or shares or 1
_nd_sc       = ((last_valid(df_fund.get("total_debt", pd.Series())) or 0)
                - (last_valid(df_fund.get("cash", pd.Series())) or 0))
_ebit_sc     = last_valid(margins.get("Operating Margin", pd.Series()))
_ebit_sc     = max(float(_ebit_sc) if not pd.isna(_ebit_sc) else 0.12, 0.02)
_rev_g_base  = float(rev_cagr_5y) if not pd.isna(rev_cagr_5y) else 0.08
_rev_g_base  = max(-0.05, min(0.40, _rev_g_base))
_capex_sc    = 0.05; _da_sc = 0.03; _nwc_sc = 0.01; _tax_sc = tax_rate_w; _n_sc = 5

def _run_scenario_dcf(g, mg, wc, tg):
    if _shares_sc <= 0 or (_rev_base_sc or 0) <= 0 or wc <= tg: return np.nan
    rv = _rev_base_sc; rv_prev = _rev_base_sc; pv = 0.0
    for y in range(1, _n_sc + 1):
        rv = rv_prev * (1 + g)
        dnwc = (rv - rv_prev) * _nwc_sc
        uf = rv * (mg * (1 - _tax_sc) + _da_sc - _capex_sc) - dnwc
        pv += uf / (1 + wc) ** y
        rv_prev = rv
    dnwc_tv = rv * tg * _nwc_sc
    uf_last = rv * (mg * (1 - _tax_sc) + _da_sc - _capex_sc) - dnwc_tv
    tv = uf_last * (1 + tg) / (wc - tg)
    eq_v = pv + tv / (1 + wc) ** _n_sc - _nd_sc
    return eq_v / _shares_sc

if _rev_base_sc and _rev_base_sc > 0:
    _scens = {
        "Bear": {"g": max(_rev_g_base - 0.08, -0.05), "mg": max(_ebit_sc - 0.04, 0.01),
                 "wc": _wacc_sc + 0.015, "tg": max(_tgr_sc - 0.005, 0.01), "prob": 0.25},
        "Base": {"g": _rev_g_base, "mg": _ebit_sc,
                 "wc": _wacc_sc,   "tg": _tgr_sc,  "prob": 0.50},
        "Bull": {"g": min(_rev_g_base + 0.06, 0.35), "mg": min(_ebit_sc + 0.04, 0.45),
                 "wc": max(_wacc_sc - 0.010, 0.05), "tg": min(_tgr_sc + 0.005, 0.04), "prob": 0.25},
    }
    for _sn, _sv in _scens.items():
        _fvs = _run_scenario_dcf(_sv["g"], _sv["mg"], _sv["wc"], _sv["tg"])
        scenario_results[_sn] = {"fair_value": _fvs, "prob": _sv["prob"]}
    _wfv_sc = sum(v["fair_value"]*v["prob"] for v in scenario_results.values()
                  if not np.isnan(v.get("fair_value", np.nan)))
    scenario_results["Weighted"] = {"fair_value": _wfv_sc if _wfv_sc > 0 else np.nan, "prob": 1.0}

# ── BVPS, EPS, DDM, RIM (per multi-model) ────────────────────────────────
bvps_s = pd.Series(dtype=float)
if "total_equity" in df_fund.columns and "shares_outstanding" in df_fund.columns:
    bvps_s = (df_fund["total_equity"] /
              df_fund["shares_outstanding"].replace(0, np.nan)).dropna()
bvps_last = last_valid(bvps_s) if not bvps_s.empty else np.nan
if np.isnan(bvps_last):
    try: bvps_last = float(mkt.get("bookValue") or np.nan)
    except: pass

ni_last3 = last_valid(df_fund.get("net_income", pd.Series()))
sh_last3 = last_valid(df_fund.get("shares_outstanding", pd.Series())) or shares or 1
eps_last3 = safe_div(ni_last3, sh_last3) if sh_last3 else np.nan
if pd.isna(eps_last3):
    try: eps_last3 = float(mkt.get("trailingEps") or np.nan)
    except: pass

tgr_rim  = 0.025
rim_fv   = np.nan
if (not np.isnan(bvps_last or np.nan) and not np.isnan(eps_last3 or np.nan)
        and (bvps_last or 0) > 0 and wacc_calc > tgr_rim):
    rim_fv = bvps_last + (eps_last3 - wacc_calc * bvps_last) / (wacc_calc - tgr_rim)
    if rim_fv <= 0 or (price and price > 0 and rim_fv > price * 10):
        rim_fv = np.nan

div_ps2 = float(mkt.get("dividendPerShare") or mkt.get("dividendRate") or 0)
tgr_ddm = 0.025
ddm_fv  = np.nan
if div_ps2 > 0 and wacc_calc > tgr_ddm:
    ddm_fv = div_ps2 * (1 + tgr_ddm) / (wacc_calc - tgr_ddm)

is_bank = any(w in sector.lower() for w in ["financial", "bank", "insurance", "capital market"])

# ── Multi-model blend ─────────────────────────────────────────────────────
_sc_wfv2 = scenario_results.get("Weighted", {}).get("fair_value", np.nan)
_dcf_fv2 = intrinsic_price_dcf if "intrinsic_price_dcf" in dir() else np.nan
if is_bank:
    _dcf_fv2 = np.nan; _sc_wfv2 = np.nan
_mult_fv2 = np.nan
if market_cap and "net_income" in df_fund.columns:
    _ni_mm = last_valid(df_fund["net_income"])
    _pe_mm = valuation.get("P/E")
    if _pe_mm and not np.isnan(_pe_mm) and _ni_mm and sh_last3:
        _mult_fv2 = (_ni_mm / sh_last3) * _pe_mm

_all_mv = {}
if not is_bank:
    if not np.isnan(_dcf_fv2 or np.nan) and (_dcf_fv2 or 0) > 0:
        _all_mv["DCF"] = (_dcf_fv2, 0.40)
    if not np.isnan(_mult_fv2 or np.nan) and (_mult_fv2 or 0) > 0:
        _all_mv["Multipli Peer"] = (_mult_fv2, 0.30)
    if not np.isnan(_sc_wfv2 or np.nan) and (_sc_wfv2 or 0) > 0:
        _all_mv["Scenario"] = (_sc_wfv2, 0.20)
    if not np.isnan(rim_fv or np.nan) and (rim_fv or 0) > 0:
        _all_mv["RIM"] = (rim_fv, 0.10)
else:
    if not np.isnan(_mult_fv2 or np.nan) and (_mult_fv2 or 0) > 0:
        _all_mv["Multipli P/E"] = (_mult_fv2, 0.35)
    if not np.isnan(bvps_last or np.nan) and (bvps_last or 0) > 0:
        _pbv_mm = valuation.get("P/B")
        if _pbv_mm and not np.isnan(_pbv_mm): _all_mv["P/BV Peer"] = (bvps_last * _pbv_mm, 0.30)
    if not np.isnan(rim_fv or np.nan) and (rim_fv or 0) > 0:
        _all_mv["RIM"] = (rim_fv, 0.20)
    if not np.isnan(ddm_fv or np.nan) and (ddm_fv or 0) > 0:
        _all_mv["DDM"] = (ddm_fv, 0.15)
if not np.isnan(ddm_fv or np.nan) and (ddm_fv or 0) > 0 and not is_bank:
    _all_mv["DDM"] = (ddm_fv, 0.10)

_tw = sum(w for _, w in _all_mv.values()) or 1
_norm_mv = {k: (v, w/_tw) for k, (v, w) in _all_mv.items()}
blend_price = sum(v * w for v, w in _norm_mv.values()) if _norm_mv else np.nan
_valid_fvs2  = [v for v, _ in _norm_mv.values()]
iv_low   = min(_valid_fvs2) if _valid_fvs2 else np.nan
iv_high  = max(_valid_fvs2) if _valid_fvs2 else np.nan
iv_cv    = (float(np.std(_valid_fvs2)) / blend_price * 100
            if len(_valid_fvs2) > 1 and not np.isnan(blend_price) and blend_price > 0
            else np.nan)
mm_confidence = ("ALTA" if not np.isnan(iv_cv) and iv_cv < 15
                 else "MEDIA" if not np.isnan(iv_cv) and iv_cv < 30
                 else "BASSA")
upside_mm = ((blend_price - price) / price) if price and not np.isnan(blend_price or np.nan) else np.nan

# ── Reverse DCF (implied growth) ──────────────────────────────────────────
implied_g = np.nan
if price and (price > 0) and _rev_base_sc and _rev_base_sc > 0 and _shares_sc > 0:
    try:
        from scipy.optimize import brentq as _brentq
        def _price_at_g(_g):
            v = _run_scenario_dcf(_g, _ebit_sc, _wacc_sc, _tgr_sc)
            return (v or 0) - price
        if _price_at_g(-0.20) * _price_at_g(0.60) < 0:
            implied_g = _brentq(_price_at_g, -0.20, 0.60, xtol=1e-4)
    except Exception: pass

# ═══════════════════════════════════════════════════════════════
# COMPANY HEADER
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
col_lg, col_inf = st.columns([1,6])
with col_lg:
    if logo_url:
        st.image(logo_url, width=72)
    else:
        st.markdown('<div style="font-size:3rem">🏢</div>', unsafe_allow_html=True)
with col_inf:
    st.markdown(f"### {company_name} &nbsp;<span class='badge'>{ticker}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='badge'>{sector}</span> &nbsp;"
                f"<span class='badge'>{industry}</span> &nbsp;"
                f"<span class='badge'>Fonte: {data_source}</span>",
                unsafe_allow_html=True)
    if description:
        with st.expander("📋 Descrizione azienda"):
            st.write(description[:900]+("…" if len(description)>900 else ""))

# KPI bar
st.markdown("")
k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: card("Prezzo",    f"${price:.2f}" if price else "N/A")
with k2: card("Market Cap", fmt_m(market_cap))
with k3: card("Revenue",   fmt_m(last_valid(df_fund.get("revenue",pd.Series()))) if "revenue" in df_fund.columns else "N/A")
with k4:
    nm_kpi = safe_div(last_valid(df_fund.get("net_income",pd.Series())),
                      last_valid(df_fund.get("revenue",pd.Series())))
    card("Net Margin", fmt_pct(nm_kpi), GREEN if (nm_kpi or 0)>0.10 else RED)
with k5: card("Beta", f"{beta:.2f}" if beta else "N/A", ORANGE)
with k6:
    roic_kpi = last_valid(roic)
    card("ROIC", fmt_pct(roic_kpi), GREEN if not pd.isna(roic_kpi) and roic_kpi>wacc_calc else RED)
st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════
SECTOR_PEERS = {
    "Technology":            ["AAPL","MSFT","GOOGL","META","NVDA","CRM","ORCL","IBM","AMZN","ADBE","INTC","AMD"],
    "Software—Application":  ["CRM","NOW","ADBE","WDAY","INTU","MSFT","ORCL","SAP"],
    "Software—Infrastructure":["MSFT","ORCL","IBM","VMW","PANW","CRWD","ZS"],
    "Semiconductors":        ["NVDA","AMD","INTC","AVGO","QCOM","MU","TSM","AMAT","ASML"],
    "Financial Services":    ["JPM","BAC","GS","MS","WFC","C","BLK","SCHW"],
    "Banks—Diversified":     ["JPM","BAC","WFC","C","USB","PNC","TFC"],
    "Insurance":             ["BRK-B","AIG","MET","PRU","AFL","TRV"],
    "Healthcare":            ["JNJ","PFE","ABBV","MRK","UNH","TMO","ABT","BMY","AMGN"],
    "Biotechnology":         ["AMGN","GILD","BIIB","REGN","VRTX","MRNA","ILMN"],
    "Drug Manufacturers":    ["PFE","ABBV","MRK","JNJ","LLY","BMY","RHHBY"],
    "Consumer Cyclical":     ["AMZN","TSLA","HD","NKE","MCD","SBUX","LOW","TGT","BKNG"],
    "Consumer Defensive":    ["PG","KO","PEP","WMT","COST","CL","GIS","K"],
    "Energy":                ["XOM","CVX","COP","SLB","EOG","OXY","MPC","VLO"],
    "Industrials":           ["HON","MMM","GE","BA","CAT","UPS","FDX","RTX","LMT"],
    "Communication Services":["GOOGL","META","NFLX","DIS","T","VZ","CMCSA","WBD"],
    "Real Estate":           ["AMT","PLD","EQIX","SPG","O","PSA","WELL"],
    "Utilities":             ["NEE","DUK","SO","D","AEP","EXC","SRE"],
    "Basic Materials":       ["LIN","APD","ECL","NEM","FCX","NUE","DOW"],
}

tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8,tab9,tab10,tab11,tab12 = st.tabs([
    "📈 Overview",
    "💰 Profittabilità",
    "🏦 Solidità & Cash Flow",
    "📊 Crescita",
    "⚙️ WACC & Beta",
    "🔮 DCF & Sensitivity",
    "🏆 Multipli & Peer",
    "🎯 Scenario & Forward",
    "🌟 Multi-Model",
    "⚠️ Risk Engine",
    "🌍 Macro & Sentiment",
    "🏁 Verdetto",
])

# ──────────────────────────────────────────────────────────────
# TAB 1 — OVERVIEW
# ──────────────────────────────────────────────────────────────
with tab1:
    section("📈","Overview — Revenue, Net Income, Free Cash Flow")
    fig_ov = make_subplots(rows=1,cols=3,
                           subplot_titles=["Revenue ($M)","Net Income ($M)","Free Cash Flow ($M)"])
    for col_idx,(cn,title) in enumerate([("revenue","Revenue"),
                                          ("net_income","Net Income"),
                                          ("free_cash_flow","Free CF")],1):
        if cn in df_fund.columns:
            s = df_fund[cn].dropna()/1e6
            c = COLORS[col_idx-1]
            fig_ov.add_trace(go.Bar(x=s.index.tolist(),y=s.values.tolist(),
                                    name=title,marker_color=c,opacity=.75,
                                    marker_line_color=BG,marker_line_width=1),row=1,col=col_idx)
            fig_ov.add_trace(go.Scatter(x=s.index.tolist(),y=s.values.tolist(),
                                        mode="lines+markers",line=dict(color=c,width=2),
                                        marker=dict(size=5),showlegend=False),row=1,col=col_idx)
    fig_ov.update_layout(**LAYOUT,height=380,
                         title_text=f"{company_name} — Overview Storico")
    fig_ov.update_yaxes(tickprefix="$",ticksuffix="M")
    st.plotly_chart(fig_ov,use_container_width=True)

    # Metriche chiave tabella
    section("📋","Metriche Chiave — Ultimo Anno")
    rows_kpi = []
    if "revenue"         in df_fund.columns: rows_kpi.append(("Revenue",           fmt_m(last_valid(df_fund["revenue"]))))
    if "gross_profit"    in df_fund.columns: rows_kpi.append(("Gross Profit",       fmt_m(last_valid(df_fund["gross_profit"]))))
    if "operating_income"in df_fund.columns: rows_kpi.append(("Operating Income",   fmt_m(last_valid(df_fund["operating_income"]))))
    if "net_income"      in df_fund.columns: rows_kpi.append(("Net Income",         fmt_m(last_valid(df_fund["net_income"]))))
    if "free_cash_flow"  in df_fund.columns: rows_kpi.append(("Free Cash Flow",     fmt_m(last_valid(df_fund["free_cash_flow"]))))
    if "total_assets"    in df_fund.columns: rows_kpi.append(("Total Assets",       fmt_m(last_valid(df_fund["total_assets"]))))
    if "total_equity"    in df_fund.columns: rows_kpi.append(("Total Equity",       fmt_m(last_valid(df_fund["total_equity"]))))
    if "total_debt"      in df_fund.columns: rows_kpi.append(("Total Debt",         fmt_m(last_valid(df_fund["total_debt"]))))
    if "cash"            in df_fund.columns: rows_kpi.append(("Cash",               fmt_m(last_valid(df_fund["cash"]))))
    rows_kpi.append(("Market Cap", fmt_m(market_cap)))
    rows_kpi.append(("Enterprise Value", fmt_m(ev)))
    c_l,c_r = st.columns(2)
    half = len(rows_kpi)//2
    with c_l:
        for label,val in rows_kpi[:half]:
            st.markdown(f"**{label}**: `{val}`")
    with c_r:
        for label,val in rows_kpi[half:]:
            st.markdown(f"**{label}**: `{val}`")

    # Dati storici raw
    with st.expander("🗃️ Dati storici completi"):
        st.dataframe(df_fund.style.format(lambda v: fmt_m(v) if not pd.isna(v) else "N/A"),
                     use_container_width=True)

# ──────────────────────────────────────────────────────────────
# TAB 2 — PROFITTABILITÀ
# ──────────────────────────────────────────────────────────────
with tab2:
    # Margini
    section("📊","Margini di Profittabilità")
    if margins:
        fig_m = go.Figure()
        for i,(name,s) in enumerate(margins.items()):
            sv = s.dropna()
            r,g,b2 = int(COLORS[i][1:3],16),int(COLORS[i][3:5],16),int(COLORS[i][5:7],16)
            fig_m.add_trace(go.Scatter(
                x=sv.index.tolist(),y=(sv*100).values.tolist(),
                mode="lines+markers",name=name,
                line=dict(color=COLORS[i],width=2.5),marker=dict(size=7),
                fill="tozeroy",fillcolor=f"rgba({r},{g},{b2},0.07)"))
        fig_m.add_hline(y=0,line_color=MUTED,line_width=.8,line_dash="dash")
        fig_m.update_layout(**LAYOUT,height=400,
                            yaxis_title="Margine (%)",yaxis_ticksuffix="%",
                            title=f"{company_name} — Trend Margini")
        plo(fig_m)

        ct,ci = st.columns([2,1])
        with ct:
            df_mt = pd.DataFrame({k:v.dropna().apply(fmt_pct) for k,v in margins.items()})
            st.dataframe(df_mt,use_container_width=True)
        with ci:
            st.markdown("**Ultimo anno:**")
            for label,key,color_c in [("Gross Margin","Gross Margin",GREEN),
                                      ("Operating Margin","Operating Margin",ACCENT),
                                      ("Net Margin","Net Margin",PURPLE)]:
                val = last_valid(margins.get(key,pd.Series()))
                if not pd.isna(val):
                    col_c = GREEN if val>0.15 else ORANGE if val>0.05 else RED
                    st.markdown(f"**{label}**: <span style='color:{col_c};font-weight:700'>{fmt_pct(val)}</span>",
                                unsafe_allow_html=True)
    else:
        st.info("Dati margini non disponibili.")

    # ROA & ROE
    st.markdown("")
    section("💰","ROA & ROE")
    if not roa.empty or not roe.empty:
        fig_rr = make_subplots(rows=1,cols=2,subplot_titles=["ROA (%)","ROE (%)"])
        for ci,(s,name,color) in enumerate([(roa,"ROA",COLORS[0]),(roe,"ROE",COLORS[1])],1):
            sv = s.dropna()
            if sv.empty: continue
            fig_rr.add_trace(go.Bar(x=sv.index.tolist(),y=(sv*100).values.tolist(),
                                    name=name,marker_color=color,opacity=.65),row=1,col=ci)
            fig_rr.add_trace(go.Scatter(x=sv.index.tolist(),y=(sv*100).values.tolist(),
                                        mode="lines+markers",line=dict(color=color,width=2),
                                        showlegend=False),row=1,col=ci)
        fig_rr.add_hline(y=0,line_color=MUTED,line_dash="dash",line_width=.8)
        fig_rr.update_yaxes(ticksuffix="%")
        plo(fig_rr,380)

    # ROIC
    section("🎯","ROIC vs WACC — Creazione di Valore")
    if not roic.dropna().empty:
        roic_pct  = roic.dropna()*100
        wacc_pct  = wacc_calc*100
        years_arr = roic_pct.index.tolist()
        roic_arr  = roic_pct.values.tolist()
        spread_arr= [r-wacc_pct for r in roic_arr]
        c_spread  = [GREEN if s>=0 else RED for s in spread_arr]

        fig_rv = make_subplots(rows=1,cols=2,
            subplot_titles=["ROIC vs WACC nel Tempo","Economic Spread (ROIC − WACC)"])
        fig_rv.add_trace(go.Scatter(x=years_arr,y=roic_arr,name="ROIC %",
                                    line=dict(color=COLORS[0],width=2.5),
                                    mode="lines+markers",marker=dict(size=7)),row=1,col=1)
        fig_rv.add_trace(go.Scatter(x=years_arr,y=[wacc_pct]*len(years_arr),
                                    name=f"WACC {wacc_pct:.0f}%",
                                    line=dict(color=RED,width=2,dash="dash"),
                                    mode="lines"),row=1,col=1)
        for i in range(len(years_arr)-1):
            cf2 = "rgba(63,185,80,.15)" if roic_arr[i]>=wacc_pct else "rgba(247,129,102,.15)"
            fig_rv.add_shape(type="rect",x0=years_arr[i],x1=years_arr[i+1],
                             y0=min(roic_arr[i],wacc_pct),y1=max(roic_arr[i],wacc_pct),
                             fillcolor=cf2,line_width=0,row=1,col=1)
        fig_rv.add_trace(go.Bar(x=years_arr,y=spread_arr,name="Spread",
                                marker_color=c_spread,opacity=.75),row=1,col=2)
        fig_rv.add_hline(y=0,line_color=MUTED,line_dash="dash",row=1,col=2)
        fig_rv.update_yaxes(ticksuffix="%")
        plo(fig_rv,420)

        roic_last   = last_valid(roic)
        spread_last = roic_last*100-wacc_pct if not pd.isna(roic_last) else np.nan
        if not pd.isna(spread_last):
            m1,m2,m3 = st.columns(3)
            with m1: card("ROIC (ultimo)", fmt_pct(roic_last), GREEN if roic_last>wacc_calc else RED)
            with m2: card("WACC (calc.)", fmt_pct(wacc_calc))
            with m3: card("Spread",f"{spread_last:+.1f}%", GREEN if spread_last>=0 else RED)
            v_roic = "✅ Value Creation" if spread_last>=0 else "⚠️ Value Destruction"
            st.markdown(f"**{v_roic}** — Spread ROIC−WACC: `{spread_last:+.1f}%`")
    else:
        st.info("Dati ROIC non disponibili.")

# ──────────────────────────────────────────────────────────────
# TAB 3 — SOLIDITÀ FINANZIARIA
# ──────────────────────────────────────────────────────────────
with tab3:
    section("🏦","Liquidità & Solvibilità")
    if liq:
        fig_lq = make_subplots(rows=2,cols=2,
                               subplot_titles=list(liq.keys())[:4])
        pos = [(1,1),(1,2),(2,1),(2,2)]
        thresh_map = {
            "Current Ratio":    [(1,"red"),(2,"green")],
            "D/E Ratio":        [(1,"green"),(2,"orange"),(3,"red")],
            "Net Debt/EBITDA":  [(2,"green"),(4,"red")],
            "Interest Coverage":[(2,"red"),(5,"green")],
        }
        for i,(key,s) in enumerate(list(liq.items())[:4]):
            sv = s.dropna()
            if sv.empty: continue
            r,c2 = pos[i]
            col2 = COLORS[i%len(COLORS)]
            fig_lq.add_trace(go.Bar(x=sv.index.tolist(),y=sv.values.tolist(),
                                    name=key,marker_color=col2,opacity=.65),row=r,col=c2)
            fig_lq.add_trace(go.Scatter(x=sv.index.tolist(),y=sv.values.tolist(),
                                        mode="lines+markers",line=dict(color=col2,width=2),
                                        showlegend=False),row=r,col=c2)
            for tv,tc in thresh_map.get(key,[]):
                fig_lq.add_hline(y=tv,line_color=tc,line_dash="dot",
                                 line_width=.9,row=r,col=c2)
        fig_lq.update_layout(**LAYOUT,height=520,showlegend=False)
        st.plotly_chart(fig_lq,use_container_width=True)

        mc1,mc2,mc3,mc4 = st.columns(4)
        for col2,key in zip([mc1,mc2,mc3,mc4],list(liq.keys())[:4]):
            v = last_valid(liq[key])
            with col2: card(key, fmt_x(v) if not pd.isna(v) else "N/A")
    else:
        st.info("Dati liquidità non disponibili.")

    # Cash Flow Quality
    st.markdown("")
    section("💵","Qualità del Cash Flow")
    fig_cf = make_subplots(rows=1,cols=2,
                           subplot_titles=["Cash Flows Assoluti ($M)","Ratio Cash Flow (%)"])
    for lbl,cn,col2 in [("Operating CF","operating_cf",COLORS[0]),
                          ("Net Income","net_income",COLORS[1]),
                          ("Free CF","free_cash_flow",COLORS[2])]:
        if cn in df_fund.columns:
            sv = df_fund[cn].dropna()/1e6
            fig_cf.add_trace(go.Scatter(x=sv.index.tolist(),y=sv.values.tolist(),
                                        name=lbl,line=dict(color=col2,width=2),
                                        mode="lines+markers",marker=dict(size=5)),row=1,col=1)
    fig_cf.add_hline(y=0,line_color=MUTED,line_dash="dash",row=1,col=1)
    for lbl,key,col2 in [("CFO/NI","CFO/Net Income",COLORS[3]),
                           ("FCF Margin","FCF Margin",COLORS[4])]:
        if key in cf_metrics:
            sv = cf_metrics[key].dropna()
            fig_cf.add_trace(go.Scatter(x=sv.index.tolist(),y=(sv*100).values.tolist(),
                                        name=lbl,line=dict(color=col2,width=2),
                                        mode="lines+markers",marker=dict(size=5)),row=1,col=2)
    fig_cf.update_yaxes(tickprefix="$",ticksuffix="M",row=1,col=1)
    fig_cf.update_yaxes(ticksuffix="%",row=1,col=2)
    plo(fig_cf,380)

    cm1,cm2,cm3 = st.columns(3)
    with cm1:
        v = last_valid(cf_metrics.get("FCF Margin",pd.Series()))
        card("FCF Margin",fmt_pct(v),GREEN if not pd.isna(v) and v>0.10 else RED)
    with cm2:
        v2 = last_valid(cf_metrics.get("CFO/Net Income",pd.Series()))
        card("CFO/Net Income",fmt_x(v2),GREEN if not pd.isna(v2) and v2>1 else RED)
    with cm3:
        v3 = last_valid(cf_metrics.get("CapEx Intensity",pd.Series()))
        card("CapEx/Revenue",fmt_pct(v3))

    # Activity Ratios
    st.markdown("")
    section("🔄","Activity Ratios — Efficienza Operativa")
    if activity:
        _act_cols = list(activity.keys())
        _act_yrs  = sorted(set(y for s in activity.values() for y in s.dropna().index))[-8:]
        if _act_yrs:
            _act_rows = {}
            for _ak2, _av2 in activity.items():
                _fmt_a = "{:.1f}x" if "Turnover" in _ak2 else "{:.0f} gg" if "days" in _ak2.lower() or "(days)" in _ak2 else "{:.2f}x"
                _act_rows[_ak2] = {yr: (_fmt_a.format(_av2.get(yr, np.nan)) if yr in _av2.index and not np.isnan(_av2.get(yr, np.nan)) else "—") for yr in _act_yrs}
            st.dataframe(pd.DataFrame(_act_rows).T, use_container_width=True)

            fig_act = go.Figure()
            _act_plt = {k: v for k, v in activity.items() if "days" in k.lower() or "(days)" in k}
            for _i, (_ak3, _av3) in enumerate(_act_plt.items()):
                _sv3 = _av3.dropna()
                if not _sv3.empty:
                    fig_act.add_trace(go.Bar(x=_sv3.index.tolist(), y=_sv3.values.tolist(),
                        name=_ak3, marker_color=COLORS[_i % len(COLORS)], opacity=0.75))
            if not fig_act.data:
                for _i2, (_ak4, _av4) in enumerate(list(activity.items())[:3]):
                    _sv4 = _av4.dropna()
                    if not _sv4.empty:
                        fig_act.add_trace(go.Scatter(x=_sv4.index.tolist(), y=_sv4.values.tolist(),
                            mode="lines+markers", name=_ak4, line=dict(color=COLORS[_i2 % len(COLORS)], width=2)))
            fig_act.update_layout(**LAYOUT, height=320, barmode="group",
                title=f"{ticker} — Activity Ratios Storici",
                yaxis_title="Valore")
            st.plotly_chart(fig_act, use_container_width=True)
    else:
        st.info("Activity ratios non disponibili (spesso N/A per aziende tech/software prive di inventario significativo).")

# ──────────────────────────────────────────────────────────────
# TAB 4 — CRESCITA
# ──────────────────────────────────────────────────────────────
with tab4:
    section("📈","Crescita & CAGR")
    if growth:
        keys5 = {k:v for k,v in growth.items() if "5y" in k}
        plot_g = keys5 if keys5 else {k:v for k,v in growth.items() if "3y" in k}
        if plot_g:
            sorted_g = dict(sorted(plot_g.items(),key=lambda x:x[1] if not pd.isna(x[1]) else -99))
            fig_gr = go.Figure(go.Bar(
                y=list(sorted_g.keys()),
                x=[v*100 if not pd.isna(v) else 0 for v in sorted_g.values()],
                orientation="h",
                marker_color=[GREEN if (v or 0)>=0 else RED for v in sorted_g.values()],
                opacity=.82,
                text=[f"{v*100:.1f}%" if not pd.isna(v) else "N/A" for v in sorted_g.values()],
                textposition="outside"
            ))
            fig_gr.add_vline(x=0,  line_color=MUTED)
            fig_gr.add_vline(x=10, line_color="rgba(63,185,80,.4)",line_dash="dot")
            fig_gr.add_vline(x=20, line_color="rgba(63,185,80,.7)",line_dash="dot")
            fig_gr.update_layout(**LAYOUT,xaxis_title="CAGR (%)",
                                 xaxis_ticksuffix="%",height=340,
                                 title=f"{ticker} — CAGR per Metrica")
            plo(fig_gr)

        # Revenue growth chart YoY
        if "revenue" in df_fund.columns:
            section("📊","Revenue YoY Growth")
            rev = df_fund["revenue"].dropna()
            yoy = rev.pct_change()*100
            fig_yoy = go.Figure()
            fig_yoy.add_trace(go.Bar(x=rev.index.tolist(),y=(rev.values/1e6).tolist(),
                                     name="Revenue ($M)",marker_color=ACCENT,opacity=.65,
                                     yaxis="y1"))
            fig_yoy.add_trace(go.Scatter(x=yoy.index.tolist(),y=yoy.values.tolist(),
                                         name="YoY %",line=dict(color=GREEN,width=2.5),
                                         mode="lines+markers",marker=dict(size=7),
                                         yaxis="y2"))
            fig_yoy.update_layout(**LAYOUT, height=380,
                title=f"{company_name} — Revenue & Crescita YoY")
            fig_yoy.update_layout(
                yaxis=dict(title="Revenue ($M)", gridcolor=GRID_C, linecolor=GRID_C),
                yaxis2=dict(title="YoY %", overlaying="y", side="right",
                            ticksuffix="%", gridcolor=GRID_C))
            st.plotly_chart(fig_yoy,use_container_width=True)

        # Tabella CAGR
        cagr_rows=[]
        for n in [3,5,7]:
            row_d={"Periodo":f"{n} anni"}
            for met,label in [("Revenue","Rev"),("Net Income","NI"),("FCF","FCF"),("EBITDA","EBITDA")]:
                k=f"{met} CAGR {n}y"
                row_d[label]=fmt_pct(growth.get(k,np.nan)) if k in growth else "N/A"
            cagr_rows.append(row_d)
        st.dataframe(pd.DataFrame(cagr_rows).set_index("Periodo"),use_container_width=True)
    else:
        st.info("Dati crescita non disponibili.")

# ──────────────────────────────────────────────────────────────
# TAB 5 — WACC & BETA (NEW)
# ──────────────────────────────────────────────────────────────
with tab5:
    section("⚙️","Beta OLS & Blume Adjustment")
    b1,b2,b3,b4 = st.columns(4)
    with b1: card("Beta OLS (5Y wkly)", f"{beta_ols:.3f}", ACCENT if abs(beta_ols-1)<0.3 else ORANGE)
    with b2: card("Beta Blume (adj)", f"{beta_blume:.3f}", ACCENT)
    with b3: card("Beta yfinance", f"{float(beta):.2f}" if beta else "N/A", MUTED)
    with b4: card("R² Regressione", f"{r_sq_ols:.3f}", GREEN if r_sq_ols > 0.3 else ORANGE)

    if len(beta_ret_x) > 10:
        xl = np.linspace(beta_ret_x.min(), beta_ret_x.max(), 100)
        yl = beta_ols * xl + (beta_ret_y.mean() - beta_ols * beta_ret_x.mean())
        fig_beta = go.Figure()
        fig_beta.add_trace(go.Scatter(x=beta_ret_x.tolist(), y=beta_ret_y.tolist(),
            mode="markers", marker=dict(color=ACCENT, opacity=0.4, size=5), name="Weekly returns"))
        fig_beta.add_trace(go.Scatter(x=xl.tolist(), y=yl.tolist(),
            mode="lines", line=dict(color=RED, width=2.5),
            name=f"OLS: β={beta_ols:.2f}  R²={r_sq_ols:.2f}"))
        fig_beta.add_vline(x=0, line_color=MUTED, line_dash="dash", line_width=0.8)
        fig_beta.add_hline(y=0, line_color=MUTED, line_dash="dash", line_width=0.8)
        fig_beta.update_layout(**LAYOUT, height=400,
            xaxis_title="SPY Weekly Return (%)", yaxis_title=f"{ticker} Weekly Return (%)",
            title=f"{ticker} — Beta OLS Regression (5Y Weekly, {n_obs_ols} obs)")
        st.plotly_chart(fig_beta, use_container_width=True)

    if not rolling_beta.dropna().empty:
        section("📉","Rolling Beta (60-day window)")
        fig_rb = go.Figure()
        _rb = rolling_beta.dropna()
        fig_rb.add_trace(go.Scatter(x=_rb.index.tolist(), y=_rb.values.tolist(),
            mode="lines", line=dict(color=ACCENT, width=1.8), name="Rolling Beta 60d",
            fill="tozeroy", fillcolor="rgba(88,166,255,0.07)"))
        fig_rb.add_hline(y=1.0, line_color=MUTED, line_dash="dot",
                         annotation_text="β=1 (market)", line_width=1.2)
        fig_rb.add_hline(y=beta_blume, line_color=GREEN, line_dash="dash",
                         annotation_text=f"Blume {beta_blume:.2f}", line_width=1.5)
        fig_rb.update_layout(**LAYOUT, height=300,
            yaxis_title="Beta", title=f"{ticker} — Rolling Beta vs SPY")
        st.plotly_chart(fig_rb, use_container_width=True)

    st.markdown("")
    section("💰","WACC — Weighted Average Cost of Capital")
    wc1,wc2,wc3,wc4,wc5 = st.columns(5)
    with wc1: card("Rf (10Y UST)", f"{rf_rate*100:.2f}%", MUTED)
    with wc2: card("ERP (Damodaran)", f"{erp*100:.1f}%", MUTED)
    with wc3: card("Ke (Cost of Equity)", f"{ke_calc*100:.2f}%", ACCENT)
    with wc4: card("Kd after-tax", f"{kd_calc*100:.2f}%", ORANGE)
    with wc5: card("WACC finale", f"{wacc_calc*100:.2f}%", GREEN if wacc_calc < 0.12 else RED)

    fig_wacc = go.Figure()
    _comp_labels = ["Rf", "ERP×β", "Size Prem", "= Ke", "Kd×(1-T)×D/V", "= WACC"]
    _comp_vals   = [rf_rate*100, (beta_blume*erp)*100, size_prem*100,
                    ke_calc*100, kd_calc*debt_w_wacc*100, wacc_calc*100]
    _comp_colors = [MUTED, ACCENT, PURPLE, GREEN, ORANGE, RED]
    fig_wacc.add_trace(go.Bar(x=_comp_labels, y=_comp_vals,
        marker_color=_comp_colors, opacity=0.85,
        text=[f"{v:.2f}%" for v in _comp_vals], textposition="outside"))
    fig_wacc.update_layout(**LAYOUT, height=380, yaxis_title="%",
        title=f"{ticker} — Scomposizione WACC ({wacc_calc*100:.2f}%)")
    st.plotly_chart(fig_wacc, use_container_width=True)

    with st.expander("📋 Dettaglio WACC"):
        st.markdown(f"""
| Parametro | Valore | Nota |
|-----------|--------|------|
| Risk-Free Rate | {rf_rate*100:.2f}% | 10Y US Treasury |
| ERP (Damodaran implied) | {erp*100:.1f}% | vs storico 5.5-6% |
| Beta OLS raw | {beta_ols:.3f} | 5Y weekly vs SPY |
| **Beta Blume adj** | **{beta_blume:.3f}** | 2/3×raw + 1/3×1.0 |
| Size Premium | {size_prem*100:.2f}% | Duff & Phelps |
| **Ke (Cost of Equity)** | **{ke_calc*100:.2f}%** | Rf + β×ERP + size |
| Kd pre-tax | {kd_pretax*100:.2f}% | Int.Exp / Total Debt |
| Tax Rate | {tax_rate_w*100:.1f}% | Effettivo |
| **Kd after-tax** | **{kd_calc*100:.2f}%** | Kd×(1-T) |
| E/V (equity weight) | {eq_w_wacc*100:.1f}% | MktCap/(MktCap+Debt) |
| D/V (debt weight) | {debt_w_wacc*100:.1f}% | |
| **WACC** | **{wacc_calc*100:.2f}%** | |
""")

    if dupont5:
        st.markdown("")
        section("🔍","DuPont 5-Factor ROE Decomposition")
        _dp_yrs = sorted([y for y in dupont5.get("ROE (5-step)", pd.Series()).dropna().index])
        if _dp_yrs:
            _dp_keys = ["Tax Burden","Interest Burden","EBIT Margin","Asset Turnover","Leverage"]
            _dp_colors = [ACCENT, GREEN, RED, ORANGE, PURPLE]
            fig_dp = go.Figure()
            for _dk, _dc in zip(_dp_keys, _dp_colors):
                if _dk in dupont5:
                    _ds = dupont5[_dk].dropna()
                    fig_dp.add_trace(go.Scatter(
                        x=_ds.index.tolist(), y=_ds.values.tolist(),
                        mode="lines+markers", name=_dk, line=dict(color=_dc, width=2)))
            fig_dp.update_layout(**LAYOUT, height=360,
                title=f"{ticker} — DuPont Components",
                yaxis_title="Ratio")
            st.plotly_chart(fig_dp, use_container_width=True)

            if "ROE (5-step)" in dupont5:
                _roe5 = dupont5["ROE (5-step)"].dropna()
                fig_roe5 = go.Figure()
                fig_roe5.add_trace(go.Bar(
                    x=_roe5.index.tolist(), y=(_roe5.values*100).tolist(),
                    marker_color=[GREEN if v > 0 else RED for v in _roe5.values],
                    opacity=0.8, text=[f"{v*100:.1f}%" for v in _roe5.values],
                    textposition="outside", name="ROE 5-step"))
                fig_roe5.add_hline(y=0, line_color=MUTED, line_dash="dash")
                fig_roe5.update_layout(**LAYOUT, height=300, yaxis_title="%",
                    yaxis_ticksuffix="%", title=f"{ticker} — ROE 5-Step")
                st.plotly_chart(fig_roe5, use_container_width=True)

            _dp_table = {}
            for _dk in _dp_keys + ["ROE (5-step)"]:
                if _dk in dupont5:
                    _ds2 = dupont5[_dk]
                    _fmt = fmt_pct if _dk in ["EBIT Margin","ROE (5-step)"] else fmt_x
                    _dp_table[_dk] = {yr: _fmt(_ds2.get(yr, np.nan)) for yr in _dp_yrs}
            st.dataframe(pd.DataFrame(_dp_table).T.rename_axis("Component"),
                         use_container_width=True)

# ──────────────────────────────────────────────────────────────
# TAB 6 — DCF & SENSITIVITY (ex tab5)
# ──────────────────────────────────────────────────────────────
with tab6:
    fair_values       = {}
    premium_disc      = None
    intrinsic_price_dcf = None
    fair_values       = {}
    premium_disc      = None
    intrinsic_price_dcf = None

    # Multipli
    section("💹","Multipli di Valutazione")
    if valuation:
        cv = st.columns(len(valuation))
        col_map = {"P/E":COLORS[0],"P/S":COLORS[1],"EV/EBITDA":COLORS[2],
                   "EV/Revenue":COLORS[3],"P/B":COLORS[4],"PEG":COLORS[5]}
        for col_v,(k,v) in zip(cv,valuation.items()):
            with col_v: card(k,fmt_x(v),col_map.get(k,ACCENT))

        show_k = [k for k in valuation if k!="PEG"]
        fig_vl = go.Figure(go.Bar(
            x=show_k,y=[valuation[k] for k in show_k],
            marker_color=[col_map.get(k,ACCENT) for k in show_k],
            opacity=.80,
            text=[fmt_x(valuation[k]) for k in show_k],textposition="outside"))
        fig_vl.update_layout(**LAYOUT,height=340,yaxis_title="Multiplo (x)",
                             yaxis_ticksuffix="x",
                             title=f"{company_name} — Multipli di Valutazione")
        plo(fig_vl)

        interp_mult = {
            "P/E":       [(15,"🟢 Value <15x"),(25,"🟡 Fair 15–25x"),(40,"🟠 Growth 25–40x"),(999,"🔴 >40x alto")],
            "P/S":       [(2,"🟢 <2x economico"),(6,"🟡 2–6x ragionevole"),(15,"🟠 6–15x caro"),(999,"🔴 >15x molto caro")],
            "EV/EBITDA": [(8,"🟢 <8x sottovalutato"),(15,"🟡 8–15x normale"),(25,"🟠 15–25x premium"),(999,"🔴 >25x elevato")],
            "P/B":       [(1,"🟢 <1x sotto book"),(3,"🟡 1–3x normale"),(10,"🟠 3–10x growth"),(999,"🔴 >10x speculativo")],
        }
        with st.expander("📖 Interpretazione multipli"):
            for k,v in valuation.items():
                th = interp_mult.get(k)
                if not th: continue
                msg = next((m for t,m in th if v<=t),th[-1][1])
                st.markdown(f"- **{k}** = {fmt_x(v)} → {msg}")
    else:
        st.warning("⚠️ Market Cap non disponibile — verifica ticker e FMP key")

    # P/B storico
    if market_cap and "total_equity" in df_fund.columns:
        st.markdown("")
        section("📘","Price to Book (P/B) Storico")
        eq_hist = df_fund["total_equity"].dropna()
        pb_hist = (market_cap/eq_hist.replace(0,np.nan)).dropna()
        pb_last = float(last_valid(pb_hist))
        fig_pb = go.Figure()
        fig_pb.add_trace(go.Scatter(x=pb_hist.index.tolist(),y=pb_hist.values.tolist(),
                                    mode="lines+markers+text",
                                    text=[f"{v:.1f}x" for v in pb_hist.values],
                                    textposition="top center",
                                    line=dict(color=ACCENT,width=2.2),
                                    fill="tozeroy",fillcolor="rgba(88,166,255,.08)",name="P/B"))
        for tv,tc,tl in [(1,RED,"<1x Sotto book"),(3,ORANGE,"3x Normale"),(10,GREEN,"10x Growth")]:
            fig_pb.add_hline(y=tv,line_color=tc,line_dash="dot",line_width=1.2,
                             annotation_text=tl,annotation_position="right")
        fig_pb.update_layout(**LAYOUT,height=360,
                             yaxis_title="P/B (x)",yaxis_ticksuffix="x",
                             title=f"{ticker} — P/B Storico")
        plo(fig_pb)
        pb_i = ("🟢 Sotto book" if pb_last<1 else "🟡 Normale" if pb_last<3
                else "🟠 Growth premium" if pb_last<10 else "🔴 Speculativo")
        st.markdown(f"**P/B attuale**: `{pb_last:.1f}x` → {pb_i}")
        if shares:
            bvps = last_valid(df_fund["total_equity"])/shares
            if not pd.isna(bvps):
                st.markdown(f"**Book Value per share**: `${bvps:.2f}`")

    # DCF
    st.markdown("")
    section("🔮","DCF — Discounted Cash Flow")
    if price:
        rev_cagr_auto = float(np.clip(rev_cagr_5y if not pd.isna(rev_cagr_5y) else 0.10,-0.05,0.30))
        om_hist = last_valid(margins.get("Operating Margin",pd.Series()))
        ebit_margin_def = max(float(om_hist) if not pd.isna(om_hist) else 0.15, 0.05)
        tax_rate_dcf = 0.21
        if "income_tax" in df_fund.columns and "operating_income" in df_fund.columns:
            _oi = df_fund["operating_income"].clip(lower=1)
            _tr = (df_fund["income_tax"]/_oi).clip(0,.40).dropna()
            if not _tr.empty: tax_rate_dcf = float(_tr.iloc[-1])
        capex_pct_def = 0.05
        if "capex" in df_fund.columns and "revenue" in df_fund.columns:
            _cx = (df_fund["capex"].abs()/df_fund["revenue"].replace(0,np.nan)).dropna()
            if not _cx.empty: capex_pct_def = float(_cx.iloc[-1])

        with st.expander("⚙️ Parametri DCF",expanded=False):
            d1,d2,d3 = st.columns(3)
            with d1:
                dcf_wacc   = st.slider("WACC DCF (%)",5.,20.,float(min(max(wacc_calc*100,5.),20.)),.5,key="dw")/100
                dcf_term_g = st.slider("Terminal Growth (%)",1.,6.,3.,.5,key="dtg")/100
                dcf_years  = st.slider("Anni proiezione",5,15,10,1,key="dy")
            with d2:
                dcf_ebit   = st.slider("EBIT Margin (%)",0.,50.,float(ebit_margin_def*100),.5,key="de")/100
                dcf_tax    = st.slider("Tax Rate (%)",10.,40.,float(tax_rate_dcf*100),.5,key="dt")/100
            with d3:
                dcf_capex  = st.slider("CapEx/Revenue (%)",0.,30.,float(capex_pct_def*100),.5,key="dc")/100
                g_base_pct = st.slider("Rev Growth Anno 1 (%)",-10.,60.,float(rev_cagr_auto*100*1.1),.5,key="dg1")

        dcf_rev_growth = [g_base_pct/100*(1-i*0.07) for i in range(dcf_years)]
        rev_base  = last_valid(df_fund.get("revenue",pd.Series()))
        shares_dcf = (last_valid(df_fund.get("shares_outstanding",pd.Series())) or shares or None)
        nd_dcf     = ((last_valid(df_fund.get("total_debt",pd.Series())) or 0)
                      - (last_valid(df_fund.get("cash",pd.Series())) or 0))

        if rev_base and shares_dcf and rev_base>0 and shares_dcf>0:
            proj=[]; rev_t=rev_base; pv_total=0.0
            for t in range(1,dcf_years+1):
                g_t    = dcf_rev_growth[t-1] if t<=len(dcf_rev_growth) else dcf_term_g
                rev_t  = rev_t*(1+g_t)
                nopat_t= rev_t*dcf_ebit*(1-dcf_tax)
                fcf_t  = nopat_t-rev_t*dcf_capex
                pv_t   = fcf_t/(1+dcf_wacc)**t
                pv_total+=pv_t
                proj.append({"Anno":datetime.now().year+t,"G%":g_t*100,
                             "Rev ($M)":rev_t/1e6,"NOPAT ($M)":nopat_t/1e6,
                             "FCF ($M)":fcf_t/1e6,"PV ($M)":pv_t/1e6})
            df_proj = pd.DataFrame(proj).set_index("Anno")
            fcf_last_dcf = proj[-1]["FCF ($M)"]*1e6
            if dcf_wacc>dcf_term_g:
                tv = fcf_last_dcf*(1+dcf_term_g)/(dcf_wacc-dcf_term_g)
                pv_tv = tv/(1+dcf_wacc)**dcf_years
            else:
                pv_tv=0
            ev_dcf = pv_total+pv_tv
            eq_val = ev_dcf-nd_dcf
            intrinsic_price_dcf = eq_val/shares_dcf
            fair_values["DCF"] = intrinsic_price_dcf

            with st.expander("📋 Proiezioni anno per anno"):
                st.dataframe(df_proj.style.format({
                    "G%":"{:.1f}%","Rev ($M)":"${:,.0f}M",
                    "NOPAT ($M)":"${:,.0f}M","FCF ($M)":"${:,.0f}M","PV ($M)":"${:,.0f}M"}),
                    use_container_width=True)

            d4,d5,d6 = st.columns(3)
            delta_pct = (price/intrinsic_price_dcf-1)*100 if price else 0
            with d4: card("EV (DCF)",fmt_m(ev_dcf),ACCENT)
            with d5: card("Prezzo Intrinseco DCF",f"${intrinsic_price_dcf:.2f}",
                          GREEN if price<=intrinsic_price_dcf else RED)
            with d6: card("vs Mercato",f"{delta_pct:+.1f}%",RED if delta_pct>0 else GREEN)

            # Sensitivity heatmap
            wacc_range = [dcf_wacc-0.02+i*0.01 for i in range(5)]
            tg_range   = [dcf_term_g-0.01+i*0.005 for i in range(5)]
            heat_data  = []
            for w in wacc_range:
                row_h=[]
                for tg in tg_range:
                    if w<=tg: row_h.append(np.nan); continue
                    pv_h=sum(
                        (rev_base*np.prod([1+g for g in (dcf_rev_growth[:t] or [dcf_term_g]*t)])
                         *dcf_ebit*(1-dcf_tax)-rev_base*dcf_capex)/(1+w)**t
                        for t in range(1,dcf_years+1))
                    fcf_h=(rev_base*np.prod([1+g for g in dcf_rev_growth])*dcf_ebit*(1-dcf_tax)
                           -rev_base*dcf_capex)
                    tv_h=fcf_h*(1+tg)/(w-tg)
                    ev_h=pv_h+tv_h/(1+w)**dcf_years
                    row_h.append(float((ev_h-nd_dcf)/shares_dcf))
                heat_data.append(row_h)
            df_heat=pd.DataFrame(heat_data,
                                 index=[f"{w*100:.1f}%" for w in wacc_range],
                                 columns=[f"{tg*100:.1f}%" for tg in tg_range])
            fig_heat=go.Figure(go.Heatmap(
                z=df_heat.values,x=df_heat.columns.tolist(),y=df_heat.index.tolist(),
                colorscale=[[0,"#f78166"],[.5,"#ffa657"],[1,"#3fb950"]],
                text=[[f"${v:.0f}" if not pd.isna(v) else "N/A" for v in row] for row in df_heat.values],
                texttemplate="%{text}",showscale=True))
            if price:
                fig_heat.add_annotation(text=f"Prezzo attuale: ${price:.2f}",
                    xref="paper",yref="paper",x=.5,y=1.08,showarrow=False,
                    font=dict(color=TEXT_C,size=11))
            fig_heat.update_layout(**LAYOUT,height=380,
                xaxis_title="Terminal Growth Rate",yaxis_title="WACC",
                title="Sensitivity 1 — Prezzo Intrinseco (WACC × Terminal G)")
            plo(fig_heat)

            # ── Sensitivity 2: Revenue Growth × EBIT Margin ──────────────
            st.markdown("")
            section("🔥","Sensitivity 2 — Rev Growth × EBIT Margin")
            _rg_range = [dcf_rev_growth[0] - 0.04 + i * 0.02 for i in range(5)]
            _em_range = [dcf_ebit - 0.04 + i * 0.02 for i in range(5)]
            _heat2_data = []
            for _rg in _rg_range:
                _row_h2 = []
                for _em in _em_range:
                    if _rg <= -1 or _em <= 0:
                        _row_h2.append(np.nan)
                        continue
                    _pv2 = 0.0
                    _rv2 = rev_base
                    _rv2_prev = rev_base
                    for _t2 in range(1, dcf_years + 1):
                        _gt2 = _rg * (1 - _t2 * 0.07) if _t2 <= len(dcf_rev_growth) else dcf_term_g
                        _rv2 = _rv2_prev * (1 + _gt2)
                        _np2 = _rv2 * _em * (1 - dcf_tax)
                        _fcf2 = _np2 - _rv2 * dcf_capex
                        _pv2 += _fcf2 / (1 + dcf_wacc) ** _t2
                        _rv2_prev = _rv2
                    if dcf_wacc > dcf_term_g:
                        _fcf2_last = _rv2 * _em * (1 - dcf_tax) - _rv2 * dcf_capex
                        _tv2 = _fcf2_last * (1 + dcf_term_g) / (dcf_wacc - dcf_term_g)
                        _ev2 = _pv2 + _tv2 / (1 + dcf_wacc) ** dcf_years
                    else:
                        _ev2 = _pv2
                    _row_h2.append(float((_ev2 - nd_dcf) / shares_dcf))
                _heat2_data.append(_row_h2)
            df_heat2 = pd.DataFrame(
                _heat2_data,
                index=[f"{_rg*100:.1f}%" for _rg in _rg_range],
                columns=[f"{_em*100:.1f}%" for _em in _em_range])
            fig_heat2 = go.Figure(go.Heatmap(
                z=df_heat2.values,
                x=df_heat2.columns.tolist(),
                y=df_heat2.index.tolist(),
                colorscale=[[0,"#f78166"],[.5,"#ffa657"],[1,"#3fb950"]],
                text=[[f"${v:.0f}" if not pd.isna(v) else "N/A" for v in row] for row in df_heat2.values],
                texttemplate="%{text}", showscale=True))
            if price:
                fig_heat2.add_annotation(
                    text=f"Prezzo attuale: ${price:.2f}",
                    xref="paper", yref="paper", x=.5, y=1.08, showarrow=False,
                    font=dict(color=TEXT_C, size=11))
            fig_heat2.update_layout(**LAYOUT, height=380,
                xaxis_title="EBIT Margin",
                yaxis_title="Rev Growth Anno 1",
                title="Sensitivity 2 — Prezzo Intrinseco (Rev Growth × EBIT Margin)")
            plo(fig_heat2)

        # Altri metodi Fair Value
        if shares and shares>0:
            fcf_s=df_fund.get("free_cash_flow",pd.Series()).dropna()
            if not fcf_s.empty:
                fcf_base=float(fcf_s.iloc[-min(3,len(fcf_s)):].mean())
                g_s=float(np.clip(rev_cagr_auto,0.01,0.20))
                pv_ddm=sum(fcf_base*(1+g_s)**t/(1+wacc_calc)**t for t in range(1,6))
                pv_ddm+=fcf_base*(1+g_s)**5*(1+0.03)/((wacc_calc-0.03)*(1+wacc_calc)**5)
                fair_values["DDM/FCF"]=(pv_ddm-(nd_last or 0))/shares
            ni_v=last_valid(df_fund.get("net_income",pd.Series()))
            if ni_v and ni_v>0 and shares>0:
                eps=ni_v/shares
                fair_pe=min(max(rev_cagr_5y*100*2 if not pd.isna(rev_cagr_5y) else 20,12),35)
                fair_values["P/E storico"]=eps*fair_pe

        fv_values={k:v for k,v in fair_values.items() if v and not pd.isna(v) and v>0}
        if fv_values and price:
            fv_med=float(np.median(list(fv_values.values())))
            premium_disc=(price-fv_med)/fv_med
            mos_pct=20; entry_price=fv_med*(1-mos_pct/100)
            fig_fv=go.Figure()
            for mk,fv_val in fv_values.items():
                fig_fv.add_trace(go.Bar(name=mk,x=[mk],y=[fv_val],
                                        marker_color=GREEN if price<=fv_val else RED,
                                        opacity=.8,text=f"${fv_val:.2f}",textposition="outside"))
            fig_fv.add_hline(y=price,line_color=ACCENT,line_dash="dash",
                             annotation_text=f"Prezzo attuale ${price:.2f}",line_width=2)
            fig_fv.add_hline(y=entry_price,line_color=ORANGE,line_dash="dot",
                             annotation_text=f"Entry target ${entry_price:.2f} (MOS {mos_pct}%)",
                             line_width=1.5)
            fig_fv.update_layout(**LAYOUT,height=360,yaxis_title="Prezzo ($)",
                                 title="Confronto Fair Value — Metodi multipli")
            plo(fig_fv)
            fv1,fv2,fv3=st.columns(3)
            with fv1: card("Fair Value (mediana)",f"${fv_med:.2f}",GREEN)
            with fv2: card("Prezzo attuale", f"${price:.2f}" if price else "N/A", ACCENT)
            with fv3:
                label_d="PREMIUM" if premium_disc>0 else "SCONTO"
                card(label_d,f"{abs(premium_disc)*100:.1f}%",RED if premium_disc>0 else GREEN)
    else:
        st.info("Prezzo non disponibile per il calcolo DCF.")

# ──────────────────────────────────────────────────────────────
# TAB 7 — MULTIPLI & PEER (ex tab6)
# ──────────────────────────────────────────────────────────────
with tab7:
    section("🏆","Analisi Competitor")
    user_peers = [p.strip().upper() for p in peer_input.split(",") if p.strip()] if peer_input else []
    auto_peers = [t for t in SECTOR_PEERS.get(sector,[]) if t!=ticker][:5]
    all_peers  = list(dict.fromkeys(user_peers+auto_peers))[:6]
    all_tickers= [ticker]+all_peers

    df_comp = pd.DataFrame()
    if all_peers:
        with st.spinner(f"📡 Carico dati peer ({len(all_tickers)} ticker)…"):
            df_comp = get_peer_data(tuple(all_tickers), fmp_key)

    if not df_comp.empty:
        # ── Numeric columns (for statistics) ───────────────────────────────
        _num_cols = [c for c in ["P/E","P/B","P/S","EV/EBITDA","EV/Sales","EV/FCF","Net Margin","Div Yield"]
                     if c in df_comp.columns]
        _peer_mask = df_comp.index != ticker  # exclude the analyzed ticker from statistics

        # ── Mean & Median rows (peers only, excluding the main ticker) ──────
        _peer_df  = df_comp[_peer_mask][_num_cols].apply(pd.to_numeric, errors="coerce")
        _mean_num = _peer_df.mean(skipna=True)
        _med_num  = _peer_df.median(skipna=True)

        # ── Percentile rank row for the analyzed ticker ─────────────────────
        _ticker_row = df_comp.loc[ticker] if ticker in df_comp.index else None
        _pct_row = {}
        if _ticker_row is not None:
            for _col in _num_cols:
                _col_all = df_comp[_col].dropna()
                _tk_val  = _ticker_row.get(_col, np.nan)
                if pd.isna(_tk_val) or len(_col_all) < 2:
                    _pct_row[_col] = np.nan
                else:
                    # lower multiple = cheaper (better) for valuation multiples; higher = better for margin/yield
                    _is_higher_better = _col in ["Net Margin", "Div Yield"]
                    _rank = float((_col_all < _tk_val).sum()) / len(_col_all) * 100
                    _pct_row[_col] = _rank if _is_higher_better else 100 - _rank

        # ── Build display DataFrame ─────────────────────────────────────────
        df_disp = df_comp.copy()
        if "Market Cap" in df_disp.columns:
            df_disp["Market Cap"] = df_disp["Market Cap"].apply(lambda v: fmt_m(v) if not pd.isna(v) else "N/A")
        for mc in ["P/E","P/B","P/S","EV/EBITDA","EV/Sales","EV/FCF"]:
            if mc in df_disp.columns:
                df_disp[mc] = df_disp[mc].apply(lambda v: fmt_x(v) if not pd.isna(v) else "N/A")
        if "Net Margin" in df_disp.columns:
            df_disp["Net Margin"] = df_disp["Net Margin"].apply(lambda v: fmt_pct(v) if not pd.isna(v) else "N/A")
        if "Div Yield" in df_disp.columns:
            df_disp["Div Yield"] = df_disp["Div Yield"].apply(lambda v: fmt_pct(v) if not pd.isna(v) else "N/A")

        # Build mean row (formatted)
        _mean_disp = {}
        for _c in df_disp.columns:
            if _c in ["P/E","P/B","P/S","EV/EBITDA","EV/Sales","EV/FCF"]:
                _mean_disp[_c] = fmt_x(_mean_num.get(_c, np.nan))
            elif _c == "Net Margin":
                _mean_disp[_c] = fmt_pct(_mean_num.get(_c, np.nan))
            elif _c == "Div Yield":
                _mean_disp[_c] = fmt_pct(_mean_num.get(_c, np.nan))
            else:
                _mean_disp[_c] = "—"

        # Build median row (formatted)
        _med_disp = {}
        for _c in df_disp.columns:
            if _c in ["P/E","P/B","P/S","EV/EBITDA","EV/Sales","EV/FCF"]:
                _med_disp[_c] = fmt_x(_med_num.get(_c, np.nan))
            elif _c == "Net Margin":
                _med_disp[_c] = fmt_pct(_med_num.get(_c, np.nan))
            elif _c == "Div Yield":
                _med_disp[_c] = fmt_pct(_med_num.get(_c, np.nan))
            else:
                _med_disp[_c] = "—"

        # Build percentile rank row (formatted)
        _pct_disp = {}
        for _c in df_disp.columns:
            if _c in _pct_row and not pd.isna(_pct_row.get(_c, np.nan)):
                _pct_disp[_c] = f"{_pct_row[_c]:.0f}%ile"
            else:
                _pct_disp[_c] = "—"

        # Append special rows
        df_disp.loc["─ Media Peer ─"]    = _mean_disp
        df_disp.loc["─ Mediana Peer ─"]  = _med_disp
        df_disp.loc[f"★ {ticker} %ile"]  = _pct_disp

        st.dataframe(df_disp, use_container_width=True, height=300)

        # ── Percentile summary cards ────────────────────────────────────────
        if _pct_row:
            st.markdown("**Percentile vs Peer** (100% = migliore, 0% = peggiore per quella metrica)")
            _pct_cols_show = [c for c in ["P/E","EV/EBITDA","P/S","P/B","EV/FCF","Net Margin"] if c in _pct_row and not pd.isna(_pct_row.get(c, np.nan))]
            if _pct_cols_show:
                _pc_parts = st.columns(len(_pct_cols_show))
                for _pci, (_pc_c, _pc_col) in enumerate(zip(_pct_cols_show, _pc_parts)):
                    _pv = _pct_row[_pc_c]
                    _pv_c = GREEN if _pv >= 60 else ORANGE if _pv >= 40 else RED
                    with _pc_col:
                        card(f"{_pc_c} pct", f"{_pv:.0f}%ile", _pv_c)

        # ── Bar charts with mean and median lines ────────────────────────────
        mult_plot = [(m,m) for m in ["P/E","EV/EBITDA","P/S","P/B","EV/FCF"]
                     if m in df_comp.columns and df_comp[m].dropna().shape[0]>0]
        if mult_plot:
            # Two rows of charts if >2 multiples
            _n_charts = len(mult_plot)
            _rows_c   = (_n_charts + 1) // 2 if _n_charts > 2 else 1
            _cols_c   = min(_n_charts, 2) if _n_charts > 2 else _n_charts
            fig_cp = make_subplots(rows=_rows_c, cols=_cols_c,
                                   subplot_titles=[m for _,m in mult_plot])
            for ci2, (mc, ml) in enumerate(mult_plot):
                _row_c = ci2 // _cols_c + 1
                _col_c = ci2 % _cols_c + 1
                sm = df_comp[mc].dropna()
                bc = [RED if idx == ticker else COLORS[5] for idx in sm.index]
                fig_cp.add_trace(go.Bar(x=sm.index.tolist(), y=sm.values.tolist(),
                                        marker_color=bc, opacity=.85,
                                        text=[f"{v:.1f}x" for v in sm.values],
                                        textposition="outside", name=ml,
                                        showlegend=False),
                                 row=_row_c, col=_col_c)
                # Peer median line
                _sm_peers = sm[sm.index != ticker]
                _peer_med = float(_sm_peers.median()) if not _sm_peers.empty else np.nan
                _peer_mean = float(_sm_peers.mean()) if not _sm_peers.empty else np.nan
                if not pd.isna(_peer_med):
                    fig_cp.add_hline(y=_peer_med,
                                     line_color=ORANGE, line_dash="dash", line_width=1.8,
                                     annotation_text=f"Med {_peer_med:.1f}x",
                                     annotation_font_color=ORANGE,
                                     row=_row_c, col=_col_c)
                if not pd.isna(_peer_mean):
                    fig_cp.add_hline(y=_peer_mean,
                                     line_color=ACCENT, line_dash="dot", line_width=1.5,
                                     annotation_text=f"Avg {_peer_mean:.1f}x",
                                     annotation_font_color=ACCENT,
                                     row=_row_c, col=_col_c)
            fig_cp.update_layout(**LAYOUT, height=420 * _rows_c, showlegend=False,
                                 title=f"{ticker} (rosso) vs Peer — Multipli (arancio=mediana, blu=media)")
            fig_cp.update_yaxes(ticksuffix="x")
            plo(fig_cp)

        # ── Valuation scorecard (cheap / fair / expensive per multiple) ──────
        _score_cols = ["P/E","EV/EBITDA","P/S","P/B","EV/FCF"]
        _cheap_m, _fair_m, _exp_m, _na_m = [], [], [], []
        if ticker in df_comp.index:
            for _sc_col in _score_cols:
                if _sc_col not in df_comp.columns:
                    _na_m.append(_sc_col); continue
                _tk_v = df_comp.loc[ticker, _sc_col]
                _peer_vals = df_comp[_peer_mask][_sc_col].dropna()
                _pm2 = float(_peer_vals.median()) if not _peer_vals.empty else np.nan
                if pd.isna(_tk_v) or pd.isna(_pm2):
                    _na_m.append(_sc_col); continue
                _prem = (_tk_v - _pm2) / abs(_pm2) if _pm2 != 0 else 0
                if _prem < -0.10:   _cheap_m.append(_sc_col)
                elif _prem > 0.10:  _exp_m.append(_sc_col)
                else:               _fair_m.append(_sc_col)

        if _cheap_m or _fair_m or _exp_m:
            st.markdown("")
            section("🏷️", "Valuation Scorecard vs Mediana Peer")
            _vs1, _vs2, _vs3 = st.columns(3)
            with _vs1:
                st.markdown(f"<span style='color:{GREEN};font-weight:700'>✅ Economico (<-10%)</span>", unsafe_allow_html=True)
                for _v in _cheap_m: st.markdown(f"- {_v}")
            with _vs2:
                st.markdown(f"<span style='color:{ORANGE};font-weight:700'>🟡 Fair (±10%)</span>", unsafe_allow_html=True)
                for _v in _fair_m: st.markdown(f"- {_v}")
            with _vs3:
                st.markdown(f"<span style='color:{RED};font-weight:700'>🔴 Costoso (>+10%)</span>", unsafe_allow_html=True)
                for _v in _exp_m: st.markdown(f"- {_v}")
            _tot_vs = len(_cheap_m) + len(_fair_m) + len(_exp_m)
            if _tot_vs > 0:
                _vs_verdict = ("POTENZIALMENTE SOTTOVALUTATO" if len(_cheap_m) > len(_exp_m)
                               else "POTENZIALMENTE SOPRAVVALUTATO" if len(_exp_m) > len(_cheap_m)
                               else "IN LINEA con la mediana dei peer")
                _vs_col = GREEN if len(_cheap_m) > len(_exp_m) else RED if len(_exp_m) > len(_cheap_m) else ORANGE
                st.markdown(f"**Verdetto relativo**: <span style='color:{_vs_col};font-weight:700'>{_vs_verdict}</span>",
                            unsafe_allow_html=True)

        # ── Radar (normalized relative to peers) ────────────────────────────
        radar_dims = [rd for rd in ["Net Margin","EV/EBITDA","P/E","P/S","P/B","EV/FCF"]
                      if rd in df_comp.columns and df_comp[rd].dropna().shape[0]>=2]
        if len(radar_dims)>=3:
            fig_rad = go.Figure()
            for i_r,(idx_r,row_r) in enumerate(df_comp.iterrows()):
                vals_r = []
                for rd in radar_dims:
                    vr = row_r.get(rd,np.nan)
                    _col_max = df_comp[rd].max()
                    if pd.isna(vr): vals_r.append(0.5)
                    elif rd in ["Net Margin","Div Yield"]:
                        vals_r.append(max(0, min(vr * 5, 1)))
                    else:
                        # for valuation multiples: lower is cheaper (score=1), higher is more expensive (score=0)
                        vals_r.append(max(0, 1 - vr / (_col_max * 1.2)) if _col_max and _col_max > 0 else 0.5)
                r2,g2,b3=int(COLORS[i_r%len(COLORS)][1:3],16),int(COLORS[i_r%len(COLORS)][3:5],16),int(COLORS[i_r%len(COLORS)][5:7],16)
                fig_rad.add_trace(go.Scatterpolar(
                    r=vals_r+[vals_r[0]],theta=radar_dims+[radar_dims[0]],
                    name=str(idx_r),
                    line=dict(color=COLORS[i_r%len(COLORS)],width=3 if idx_r==ticker else 1.5),
                    fill="toself",fillcolor=f"rgba({r2},{g2},{b3},0.06)",opacity=.85))
            fig_rad.update_layout(**LAYOUT,
                polar=dict(bgcolor=AX_BG,
                           radialaxis=dict(visible=True,range=[0,1],gridcolor=GRID_C),
                           angularaxis=dict(gridcolor=GRID_C)),
                title=f"Radar Competitivo — {ticker} vs Peer (normalizzato)",height=460)
            plo(fig_rad)
    else:
        if not all_peers:
            st.info(f"💡 Nessun peer predefinito per il settore '{sector}'. "
                    f"Aggiungi ticker manualmente nel campo **Peer Tickers** nella sidebar (es: GOOGL,META,AMZN).")
        else:
            st.warning(f"⚠️ Dati peer non disponibili per: {', '.join(all_peers)}. "
                       f"Verifica che i ticker siano corretti o riprova tra qualche secondo.")

# ──────────────────────────────────────────────────────────────
# TAB 8 — SCENARIO & FORWARD
# ──────────────────────────────────────────────────────────────
with tab8:
    section("🎯","Scenario Analysis — Bear / Base / Bull")
    if scenario_results:
        # ── Weighted Average Fair Value — prominent KPI cards ───────────────
        _wfv_sc2  = scenario_results.get("Weighted", {}).get("fair_value", np.nan)
        _bear_fv  = scenario_results.get("Bear", {}).get("fair_value", np.nan)
        _base_fv  = scenario_results.get("Base", {}).get("fair_value", np.nan)
        _bull_fv  = scenario_results.get("Bull", {}).get("fair_value", np.nan)
        _up_wfv   = ((_wfv_sc2 - price) / price) if price and not np.isnan(_wfv_sc2 or np.nan) else np.nan
        _sc_kpi1, _sc_kpi2, _sc_kpi3, _sc_kpi4, _sc_kpi5 = st.columns(5)
        with _sc_kpi1:
            card("Bear (25%)", f"${_bear_fv:.2f}" if not np.isnan(_bear_fv or np.nan) else "N/D", RED)
        with _sc_kpi2:
            card("Base (50%)", f"${_base_fv:.2f}" if not np.isnan(_base_fv or np.nan) else "N/D", ORANGE)
        with _sc_kpi3:
            card("Bull (25%)", f"${_bull_fv:.2f}" if not np.isnan(_bull_fv or np.nan) else "N/D", GREEN)
        with _sc_kpi4:
            card("Weighted Avg FV", f"${_wfv_sc2:.2f}" if not np.isnan(_wfv_sc2 or np.nan) else "N/D",
                 GREEN if not np.isnan(_up_wfv or np.nan) and (_up_wfv or 0) > 0 else RED)
        with _sc_kpi5:
            card("Upside (Weighted)", f"{_up_wfv*100:+.1f}%" if not np.isnan(_up_wfv or np.nan) else "N/D",
                 GREEN if not np.isnan(_up_wfv or np.nan) and (_up_wfv or 0) > 0 else RED)
        st.markdown("")

        # ── Full scenario table ──────────────────────────────────────────────
        _sc_rows2 = []
        _rev_base_sc_disp = _rev_base_sc or 0
        for _sn3, _sv3 in scenario_results.items():
            _fv3 = _sv3.get("fair_value", np.nan)
            _up3 = ((_fv3 - price) / price) if price and not np.isnan(_fv3 or np.nan) else np.nan
            # Estimate FCF Y1 for display (Rev_base × (1+g) × EBIT × (1-T) − CapEx)
            _sc_g3  = _scens.get(_sn3, {}).get("g", 0) if "_scens" in dir() and _sn3 in ("Bear","Base","Bull") else np.nan
            _sc_mg3 = _scens.get(_sn3, {}).get("mg", 0) if "_scens" in dir() and _sn3 in ("Bear","Base","Bull") else np.nan
            if not np.isnan(_sc_g3) and _rev_base_sc_disp > 0:
                _rev_y1 = _rev_base_sc_disp * (1 + _sc_g3)
                _fcf_y1 = _rev_y1 * (_sc_mg3 * (1 - _tax_sc) + _da_sc - _capex_sc)
                _fcf_disp = fmt_m(_fcf_y1)
            else:
                _fcf_disp = "—"
            _sc_rows2.append({
                "Scenario": _sn3,
                "Rev Growth": (f"{_sc_g3*100:.1f}%" if not np.isnan(_sc_g3) else "—"),
                "EBIT Margin": (f"{_sc_mg3*100:.1f}%" if not np.isnan(_sc_mg3) else "—"),
                "FCF Y1 (est)": _fcf_disp,
                "Fair Value": f"${_fv3:.2f}" if not np.isnan(_fv3 or np.nan) else "N/D",
                "Probabilità": f"{int(_sv3['prob']*100)}%" if _sv3['prob'] < 1 else "Ponderato",
                "Upside": f"{_up3:+.1%}" if not np.isnan(_up3 or np.nan) else "N/D",
            })
        st.dataframe(pd.DataFrame(_sc_rows2).set_index("Scenario"), use_container_width=True)

        _plot_sc = {k: v for k, v in scenario_results.items()
                    if k != "Weighted" and not np.isnan(v.get("fair_value", np.nan) or np.nan)}
        if _plot_sc:
            fig_sc = go.Figure()
            _sc_colors = {"Bear": RED, "Base": ORANGE, "Bull": GREEN}
            _sc_fvs = [v["fair_value"] for v in _plot_sc.values()]
            for _sn4, _sv4 in _plot_sc.items():
                _fv4 = _sv4["fair_value"]
                _c4  = _sc_colors.get(_sn4, ACCENT)
                fig_sc.add_trace(go.Bar(
                    x=[_sn4], y=[_fv4], marker_color=_c4, opacity=0.8,
                    text=[f"${_fv4:.2f}"], textposition="outside", name=_sn4))
            if price: fig_sc.add_hline(y=price, line_color=ACCENT, line_dash="dash",
                                        line_width=2, annotation_text=f"Prezzo ${price:.2f}")
            _wfv3 = scenario_results.get("Weighted", {}).get("fair_value", np.nan)
            if not np.isnan(_wfv3 or np.nan):
                fig_sc.add_hline(y=_wfv3, line_color=GREEN, line_dash="dot",
                                  line_width=2, annotation_text=f"Weighted ${_wfv3:.2f}")
            fig_sc.update_layout(**LAYOUT, height=400, yaxis_title="Fair Value ($)",
                title=f"{ticker} — Scenario Analysis (Rev Growth × EBIT Margin)")
            st.plotly_chart(fig_sc, use_container_width=True)

            with st.expander("⚙️ Parametri scenari"):
                st.markdown(f"""
| | Bear | Base | Bull |
|---|---|---|---|
| Rev Growth | {max(_rev_g_base-0.08,-0.05)*100:.1f}% | {_rev_g_base*100:.1f}% | {min(_rev_g_base+0.06,0.35)*100:.1f}% |
| EBIT Margin | {max(_ebit_sc-0.04,0.01)*100:.1f}% | {_ebit_sc*100:.1f}% | {min(_ebit_sc+0.04,0.45)*100:.1f}% |
| WACC | {(_wacc_sc+0.015)*100:.2f}% | {_wacc_sc*100:.2f}% | {max(_wacc_sc-0.010,0.05)*100:.2f}% |
| TGR | {max(_tgr_sc-0.005,0.01)*100:.1f}% | {_tgr_sc*100:.1f}% | {min(_tgr_sc+0.005,0.04)*100:.1f}% |
| Probabilità | 25% | 50% | 25% |
""")
    else:
        st.info("Dati insufficienti per scenario analysis (serve revenue history).")

    st.markdown("")
    section("🔄","Reverse DCF — Crescita Implicita nel Prezzo")
    ri1, ri2, ri3 = st.columns(3)
    with ri1: card("Crescita implicita", f"{implied_g*100:.1f}%" if not np.isnan(implied_g or np.nan) else "N/D",
                   GREEN if not np.isnan(implied_g or np.nan) and implied_g < _rev_g_base else RED)
    with ri2: card("Crescita storica (5Y)", f"{_rev_g_base*100:.1f}%", ACCENT)
    with ri3:
        if not np.isnan(implied_g or np.nan):
            _diff = implied_g - _rev_g_base
            _rev_lbl = ("Mercato CONSERVATIVO — possibile upside" if _diff < -0.02
                       else "Mercato RAGIONEVOLE — fairly priced" if abs(_diff) <= 0.02
                       else "Mercato AGGRESSIVO — richiede esecuzione perfetta")
            card("Giudizio", "👆 Vedi sotto", ACCENT)
            st.markdown(f"<div style='font-size:.85rem;margin-top:8px'>{_rev_lbl}</div>",
                        unsafe_allow_html=True)

    st.markdown("")
    section("📅","Forward Expectations (yfinance)")
    _fwd = fwd_data
    f1,f2,f3,f4 = st.columns(4)
    with f1: card("Forward P/E", fmt_x(_fwd.get("forwardPE")), ACCENT)
    with f2: card("Forward EPS", f"${_fwd.get('forwardEps',0) or 0:.2f}" if _fwd.get("forwardEps") else "N/A", GREEN)
    with f3: card("EPS Growth (fwd)", fmt_pct(_fwd.get("earningsGrowth")), GREEN if (_fwd.get("earningsGrowth") or 0) > 0 else RED)
    with f4: card("Rev Growth (fwd)", fmt_pct(_fwd.get("revenueGrowth")), GREEN if (_fwd.get("revenueGrowth") or 0) > 0 else RED)

    if _fwd.get("targetMeanPrice"):
        st.markdown("")
        fa1, fa2, fa3, fa4 = st.columns(4)
        with fa1: card("Target Low", f"${_fwd.get('targetLowPrice',0):.2f}" if _fwd.get("targetLowPrice") else "N/A", MUTED)
        with fa2: card("Target Mean", f"${_fwd.get('targetMeanPrice',0):.2f}" if _fwd.get("targetMeanPrice") else "N/A", ACCENT)
        with fa3: card("Target High", f"${_fwd.get('targetHighPrice',0):.2f}" if _fwd.get("targetHighPrice") else "N/A", GREEN)
        with fa4:
            _n_analysts = _fwd.get("numberOfAnalystOpinions")
            card("N° Analisti", str(_n_analysts) if _n_analysts else "N/A", MUTED)
        if _fwd.get("targetMeanPrice") and price:
            _pt_upside = (_fwd["targetMeanPrice"] - price) / price
            _pt_col = GREEN if _pt_upside > 0 else RED
            st.markdown(f"**Analyst consensus upside**: <span style='color:{_pt_col};font-weight:700'>{_pt_upside:+.1%}</span> (target medio ${_fwd['targetMeanPrice']:.2f})",
                        unsafe_allow_html=True)

    rec_key = _fwd.get("recommendationKey", "")
    if rec_key:
        _rec_map = {"strongBuy":"✅ STRONG BUY","buy":"✅ BUY","hold":"⏳ HOLD",
                    "sell":"❌ SELL","strongSell":"❌ STRONG SELL"}
        st.markdown(f"**Raccomandazione consensus**: {_rec_map.get(rec_key, rec_key.upper())}")

    st.markdown("")
    section("📊","Quality of Earnings")
    if not df_quality.empty:
        def _qoe_color(col, v):
            if pd.isna(v): return ""
            if col == "CFO/NI": return f"color: {'#3fb950' if v >= 1 else '#ffa657' if v >= 0.5 else '#f78166'}"
            if col == "FCF/NI": return f"color: {'#3fb950' if v >= 0.8 else '#ffa657' if v >= 0.4 else '#f78166'}"
            if col == "Accruals": return f"color: {'#3fb950' if abs(v) < 0.05 else '#ffa657' if abs(v) < 0.08 else '#f78166'}"
            return ""
        _qoe_fmt = {
            "NI ($M)":  "{:,.0f}", "CFO ($M)": "{:,.0f}", "FCF ($M)": "{:,.0f}",
            "CFO/NI":   "{:.2f}x", "FCF/NI":   "{:.2f}x", "Accruals": "{:.4f}",
        }
        try:
            st.dataframe(
                df_quality.style.format(_qoe_fmt, na_rep="N/D")
                .applymap(lambda v: _qoe_color("CFO/NI", v), subset=["CFO/NI"])
                .applymap(lambda v: _qoe_color("FCF/NI", v), subset=["FCF/NI"])
                .applymap(lambda v: _qoe_color("Accruals", v), subset=["Accruals"]),
                use_container_width=True)
        except Exception:
            st.dataframe(df_quality.style.format(_qoe_fmt, na_rep="N/D"),
                         use_container_width=True)
    else:
        st.info("Dati Quality of Earnings non disponibili.")

# ──────────────────────────────────────────────────────────────
# TAB 9 — MULTI-MODEL VALUATION
# ──────────────────────────────────────────────────────────────
with tab9:
    section("🌟","Valore Intrinseco Finale — Multi-Model Blend")
    if blend_price and not np.isnan(blend_price):
        mm1,mm2,mm3,mm4 = st.columns(4)
        with mm1: card("Blend Price", f"${blend_price:.2f}", GREEN if (upside_mm or 0) > 0 else RED)
        with mm2: card("Prezzo Attuale", f"${price:.2f}" if price else "N/A", ACCENT)
        with mm3: card("Upside/Downside", f"{(upside_mm or 0)*100:+.1f}%",
                       GREEN if (upside_mm or 0) > 0.05 else RED if (upside_mm or 0) < -0.05 else ORANGE)
        with mm4: card("Confidenza", mm_confidence,
                       GREEN if mm_confidence == "ALTA" else ORANGE if mm_confidence == "MEDIA" else RED)

        # Gauge
        _g_color = ("#1a6b2e" if (upside_mm or 0) > 0.20
                    else "#4caf50" if (upside_mm or 0) > 0.05
                    else "#888800" if abs(upside_mm or 0) <= 0.05
                    else "#cc4400" if (upside_mm or 0) > -0.20
                    else "#8b0000")
        _v_label = ("SOTTOVALUTATA" if (upside_mm or 0) > 0.20
                    else "LIEV. SOTTO" if (upside_mm or 0) > 0.05
                    else "FAIRLY VALUED" if abs(upside_mm or 0) <= 0.05
                    else "LIEV. SOPRA" if (upside_mm or 0) > -0.20
                    else "SOPRAVVALUTATA")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=(upside_mm or 0) * 100,
            delta={"reference": 0, "valueformat": ".1f", "suffix": "%"},
            number={"suffix": "%", "font": {"color": TEXT_C, "size": 36}},
            gauge={
                "axis": {"range": [-60, 60], "tickcolor": TEXT_C, "ticksuffix": "%"},
                "bar":  {"color": _g_color, "thickness": 0.3},
                "bgcolor": AX_BG,
                "steps": [
                    {"range": [-60, -20], "color": "#4a0000"},
                    {"range": [-20,  -5], "color": "#4a1500"},
                    {"range": [  -5,  5], "color": "#2a2a00"},
                    {"range": [   5, 20], "color": "#0a3a0a"},
                    {"range": [  20, 60], "color": "#003a00"},
                ],
                "threshold": {"line": {"color": "white", "width": 3}, "value": 0},
            },
            title={"text": f"Upside/Downside vs {'$'+f'{price:.2f}' if price else 'N/A'}<br><b>{_v_label}</b>",
                   "font": {"color": TEXT_C, "size": 14}},
        ))
        fig_gauge.update_layout(**LAYOUT, height=380)
        st.plotly_chart(fig_gauge, use_container_width=True)

        # Tabella modelli
        st.markdown("")
        section("📊","Dettaglio Modelli")
        _mv_rows = []
        for _mn5, (_mv5, _mw5) in _norm_mv.items():
            _up5 = ((_mv5 - price) / price) if price and not np.isnan(_mv5) else np.nan
            _mv_rows.append({
                "Modello": _mn5,
                "Fair Value": f"${_mv5:.2f}" if not np.isnan(_mv5) else "N/D",
                "Peso (norm.)": f"{_mw5*100:.0f}%",
                "Upside": f"{_up5:+.1%}" if not np.isnan(_up5) else "N/D",
                "Contributo": f"${_mv5*_mw5:.2f}" if not np.isnan(_mv5) else "N/D",
            })
        _mv_rows.append({
            "Modello": "▶ BLEND FINALE",
            "Fair Value": f"${blend_price:.2f}",
            "Peso (norm.)": "100%",
            "Upside": f"{(upside_mm or 0):+.1%}",
            "Contributo": f"${blend_price:.2f}",
        })
        st.dataframe(pd.DataFrame(_mv_rows).set_index("Modello"), use_container_width=True)

        # Range chart
        if not np.isnan(iv_low) and not np.isnan(iv_high):
            fig_range = go.Figure()
            fig_range.add_trace(go.Scatter(
                x=[iv_low, iv_high], y=[0.5, 0.5], mode="lines",
                line=dict(color=MUTED, width=8), name="Range"))
            for _mn6, (_mv6, _) in _norm_mv.items():
                fig_range.add_trace(go.Scatter(
                    x=[_mv6], y=[0.5], mode="markers+text",
                    text=[f"{_mn6}<br>${_mv6:.0f}"],
                    textposition="top center",
                    marker=dict(size=14, color=ACCENT), name=_mn6))
            if price:
                fig_range.add_vline(x=price, line_color=RED, line_dash="dash",
                                     line_width=2, annotation_text=f"Prezzo ${price:.2f}")
            fig_range.add_vline(x=blend_price, line_color=GREEN, line_width=2.5,
                                 annotation_text=f"Blend ${blend_price:.2f}")
            fig_range.update_layout(**LAYOUT, height=220,
                xaxis_title="Prezzo ($)", showlegend=False,
                title=f"Range valutazione: ${iv_low:.0f} — ${iv_high:.0f}")
            fig_range.update_layout(yaxis=dict(visible=False))
            st.plotly_chart(fig_range, use_container_width=True)

        with st.expander("ℹ️ Metodologia"):
            _method_txt = ("**Non-bank**: DCF FCFF (40%) + Multipli Peer (30%) + Scenario (20%) + RIM (10%)"
                           if not is_bank else
                           "**Bank**: Multipli P/E (35%) + P/BV (30%) + RIM (20%) + DDM (15%) — DCF FCFF escluso")
            st.markdown(_method_txt)
            st.markdown(f"""
- **RIM** = BVPS + (EPS − WACC×BVPS) / (WACC − TGR)  →  {'$'+f'{rim_fv:.2f}' if not np.isnan(rim_fv) else 'N/A'}
- **DDM** = D₀×(1+g) / (WACC−g)  →  {'$'+f'{ddm_fv:.2f}' if not np.isnan(ddm_fv) else 'N/A'}
- **BVPS** = {f'${bvps_last:.2f}' if (bvps_last is not None and not np.isnan(float(bvps_last))) else 'N/A'}
- **WACC usato** = {wacc_calc*100:.2f}%
""")
    else:
        st.info("Dati insufficienti per il blend multi-modello.")
        if not is_bank:
            st.markdown("**Suggerimento**: verifica che `revenue`, `operating_income` e `shares_outstanding` siano disponibili nei dati SEC.")

# ──────────────────────────────────────────────────────────────
# TAB 10 — RISK ENGINE
# ──────────────────────────────────────────────────────────────
with tab10:
    section("⚠️","Risk Dashboard")
    if risk_metrics:
        # Row 1: Ann Return, Ann Vol, Sharpe, Sortino, Calmar
        r1,r2,r3,r4,r5 = st.columns(5)
        _ann_ret_disp = risk_metrics.get("Ann. Return", np.nan)
        with r1: card("Ann. Return", fmt_pct(_ann_ret_disp),
                      GREEN if not np.isnan(_ann_ret_disp or np.nan) and (_ann_ret_disp or 0) > 0.10
                      else ORANGE if not np.isnan(_ann_ret_disp or np.nan) and (_ann_ret_disp or 0) > 0
                      else RED)
        with r2: card("Ann. Volatility", fmt_pct(risk_metrics.get("Ann. Volatility")),
                      GREEN if (risk_metrics.get("Ann. Volatility") or 1) < 0.20 else
                      ORANGE if (risk_metrics.get("Ann. Volatility") or 1) < 0.35 else RED)
        with r3: card("Sharpe Ratio", f"{risk_metrics.get('Sharpe Ratio', np.nan):.2f}" if not np.isnan(risk_metrics.get("Sharpe Ratio", np.nan)) else "N/A",
                      GREEN if (risk_metrics.get("Sharpe Ratio") or 0) > 1 else
                      ORANGE if (risk_metrics.get("Sharpe Ratio") or 0) > 0.5 else RED)
        with r4: card("Sortino Ratio", f"{risk_metrics.get('Sortino Ratio', np.nan):.2f}" if not np.isnan(risk_metrics.get("Sortino Ratio", np.nan)) else "N/A", ACCENT)
        with r5: card("Calmar Ratio", f"{risk_metrics.get('Calmar Ratio', np.nan):.2f}" if not np.isnan(risk_metrics.get("Calmar Ratio", np.nan)) else "N/A", MUTED)

        # Row 2: Max DD, VaR, CVaR, Risk Class
        r6,r7,r8,r9 = st.columns(4)
        with r6: card("Max Drawdown", fmt_pct(risk_metrics.get("Max Drawdown")),
                      GREEN if (risk_metrics.get("Max Drawdown") or -1) > -0.15 else
                      ORANGE if (risk_metrics.get("Max Drawdown") or -1) > -0.30 else RED)
        with r7: card("VaR 95% (1d)", fmt_pct(risk_metrics.get("VaR 95% (1d)")), ORANGE)
        with r8: card("CVaR 95% (1d)", fmt_pct(risk_metrics.get("CVaR 95% (1d)")), ORANGE)
        with r9: card("Risk Class", risk_class,
                      GREEN if risk_class == "LOW" else ORANGE if risk_class == "MEDIUM" else RED)

        # Price + Drawdown chart
        if not px_tk_daily.empty and len(px_tk_daily) > 30:
            st.markdown("")
            section("📉","Price & Drawdown (2Y)")
            fig_risk = go.Figure()
            fig_risk.add_trace(go.Scatter(
                x=px_tk_daily.index.tolist(), y=px_tk_daily.values.tolist(),
                mode="lines", name="Price", line=dict(color=ACCENT, width=1.8),
                yaxis="y1"))
            if not dd_series.empty:
                fig_risk.add_trace(go.Scatter(
                    x=dd_series.index.tolist(), y=(dd_series.values*100).tolist(),
                    mode="lines", name="Drawdown %", line=dict(color=RED, width=1.2),
                    fill="tozeroy", fillcolor="rgba(247,129,102,0.2)",
                    yaxis="y2"))
            fig_risk.update_layout(**LAYOUT, height=420,
                title=f"{ticker} — Price & Drawdown (Max DD: {max_dd_r*100:.1f}%)")
            fig_risk.update_layout(
                yaxis=dict(title="Price ($)", gridcolor=GRID_C),
                yaxis2=dict(title="Drawdown (%)", overlaying="y", side="right",
                            ticksuffix="%", gridcolor=GRID_C),
            )
            st.plotly_chart(fig_risk, use_container_width=True)

            # Returns distribution
            if not ret_tk_daily.empty and len(ret_tk_daily) > 30:
                st.markdown("")
                section("📊","Distribuzione Rendimenti Giornalieri")
                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(
                    x=(ret_tk_daily.values*100).tolist(), nbinsx=80,
                    marker_color=ACCENT, opacity=0.75, name="Returns",
                    histnorm="probability density"))
                if not np.isnan(var_95_r):
                    fig_dist.add_vline(x=var_95_r*100, line_color=RED, line_width=2,
                                       line_dash="dash",
                                       annotation_text=f"VaR 95%: {var_95_r*100:.2f}%")
                fig_dist.add_vline(x=0, line_color=MUTED, line_dash="dot", line_width=0.8)
                _ret_mu = ret_tk_daily.mean()*100; _ret_sd = ret_tk_daily.std()*100
                import numpy.random as _npr
                _xg = np.linspace(ret_tk_daily.min()*100, ret_tk_daily.max()*100, 200)
                from scipy.stats import norm as _snorm
                _yg = _snorm.pdf(_xg, _ret_mu, _ret_sd)
                fig_dist.add_trace(go.Scatter(x=_xg.tolist(), y=_yg.tolist(),
                    mode="lines", line=dict(color=GREEN, width=2),
                    name="Normal fit"))
                fig_dist.update_layout(**LAYOUT, height=340,
                    xaxis_title="Daily Return (%)", yaxis_title="Density",
                    title=f"{ticker} — Daily Returns Distribution (μ={_ret_mu:.2f}% σ={_ret_sd:.2f}%)")
                st.plotly_chart(fig_dist, use_container_width=True)

        # Risk table
        st.markdown("")
        section("📋","Metriche di Rischio Complete")
        _rk_rows = []
        for _rk2, _rv2 in risk_metrics.items():
            _fmt2 = f"{_rv2:.2f}" if "Ratio" in _rk2 else fmt_pct(_rv2)
            _rk_rows.append({"Metrica": _rk2, "Valore": _fmt2})
        st.dataframe(pd.DataFrame(_rk_rows).set_index("Metrica"), use_container_width=True)
    else:
        st.info("Dati storici prezzi non disponibili per calcolo risk metrics.")

# ──────────────────────────────────────────────────────────────
# TAB 11 — MACRO & SENTIMENT (ex tab7)
# ──────────────────────────────────────────────────────────────
with tab11:
    macro_verdict  = "N/A"
    sentiment_avg  = 0.0
    sent_data      = {"scores":[],"labels":[],"avg":0,"source":"N/A",
                      "headlines":[],"model":"N/A","pos_pct":0,"neg_pct":0,"neu_pct":0}
    sent_verdict   = "N/A"

    # MACRO
    section("🌍","Analisi Macroeconomica (FRED)")
    if fred_key:
        with st.spinner("📡 Carico dati FRED…"):
            gdp_s = ffr_s = cpi_s = pd.Series(dtype=float)
            macro_ok = True
            try:
                gdp_s   = get_fred_series("A191RL1Q225SBEA", fred_key)
                ffr_s   = get_fred_series("FEDFUNDS",        fred_key)
                cpi_raw = get_fred_series("CPIAUCSL",        fred_key)
                cpi_s   = cpi_raw.pct_change(12)*100 if not cpi_raw.empty else pd.Series()
            except Exception as e_fred:
                st.warning(f"⚠️ FRED: {e_fred}")
                macro_ok = False
        if macro_ok and not(gdp_s.empty and ffr_s.empty and cpi_s.empty):
            avail = [(s,t,c,u) for s,t,c,u in [
                (gdp_s,"PIL Reale YoY%",GREEN,"% YoY"),
                (ffr_s,"Fed Funds Rate",RED,"% tasso"),
                (cpi_s,"Inflazione CPI YoY%",ORANGE,"% YoY"),
            ] if not s.empty]
            if avail:
                fig_mac = make_subplots(rows=len(avail),cols=1,
                    subplot_titles=[t for _,t,_,_ in avail],shared_xaxes=True)
                for im,(sm2,tm,cm,_) in enumerate(avail,1):
                    s2=sm2.iloc[-120:]
                    fig_mac.add_trace(go.Scatter(x=s2.index.tolist(),y=s2.values.tolist(),
                        name=tm,line=dict(color=cm,width=2),
                        fill="tozeroy" if im==1 else None,
                        fillcolor="rgba(63,185,80,.05)"),row=im,col=1)
                    fig_mac.add_hline(y=0,line_color=MUTED,line_dash="dash",
                                      line_width=.8,row=im,col=1)
                fig_mac.update_layout(**LAYOUT,height=120*len(avail)+100,
                                      title="Dati Macro USA — Ultimi 10 anni")
                plo(fig_mac)
            ms = 0
            gdp_l=float(gdp_s.iloc[-1]) if not gdp_s.empty else np.nan
            ffr_l=float(ffr_s.iloc[-1]) if not ffr_s.empty else np.nan
            cpi_l=float(cpi_s.iloc[-1]) if not cpi_s.empty else np.nan
            mc1,mc2,mc3=st.columns(3)
            if not pd.isna(gdp_l):
                ms+=(1 if gdp_l>=2.5 else -1 if gdp_l<0 else 0)
                with mc1: card("PIL Reale",f"{gdp_l:.1f}%",GREEN if gdp_l>=2 else RED if gdp_l<0 else ORANGE)
            if not pd.isna(ffr_l):
                ms+=(1 if ffr_l<=2.5 else -1 if ffr_l>5 else 0)
                with mc2: card("Fed Funds Rate",f"{ffr_l:.2f}%",GREEN if ffr_l<=2.5 else RED if ffr_l>5 else ORANGE)
            if not pd.isna(cpi_l):
                ms+=(1 if cpi_l<=2.5 else -1 if cpi_l>5 else 0)
                with mc3: card("Inflazione CPI",f"{cpi_l:.1f}%",GREEN if cpi_l<=2.5 else RED if cpi_l>5 else ORANGE)
            macro_verdict=("FAVOREVOLE" if ms>=2 else "NEUTRO" if ms>=0 else "SFAVOREVOLE")
            mc=GREEN if macro_verdict=="FAVOREVOLE" else RED if macro_verdict=="SFAVOREVOLE" else ORANGE
            st.markdown(f"**Macro**: <span style='color:{mc}'>{macro_verdict}</span> per il settore {sector}",
                        unsafe_allow_html=True)
    else:
        st.info("💡 Inserisci una FRED API key per i dati macroeconomici.")

    # SENTIMENT
    st.markdown("")
    section("📰","Sentiment Analysis — News Finanziarie")
    with st.spinner(f"📡 Analizzo news per {ticker}…"):
        sent_data = get_news_sentiment(ticker, company_name, news_key)
    sentiment_avg = sent_data.get("avg",0.0)
    sent_verdict  = ("MOLTO POSITIVO" if sentiment_avg>=0.4 else
                     "POSITIVO"       if sentiment_avg>=0.1 else
                     "NEUTRO"         if sentiment_avg>=-0.1 else
                     "NEGATIVO"       if sentiment_avg>=-0.4 else "MOLTO NEGATIVO")
    sc=GREEN if sentiment_avg>=0.1 else RED if sentiment_avg<=-0.1 else ORANGE

    ss1,ss2,ss3,ss4=st.columns(4)
    with ss1: card("Score Medio",f"{sentiment_avg:+.2f}",sc)
    with ss2: card("Positivo %",f"{sent_data.get('pos_pct',0):.0f}%",GREEN)
    with ss3: card("Negativo %",f"{sent_data.get('neg_pct',0):.0f}%",RED)
    with ss4: card("Neutro %",f"{sent_data.get('neu_pct',0):.0f}%",ORANGE)

    if sent_data.get("scores"):
        fig_gauge=go.Figure(go.Indicator(
            mode="gauge+number",value=sentiment_avg,
            gauge=dict(axis=dict(range=[-1,1],tickcolor=TEXT_C),
                       bar=dict(color=sc),
                       steps=[dict(range=[-1,-.1],color=RED),
                               dict(range=[-.1,.1],color=ORANGE),
                               dict(range=[.1,1],color=GREEN)]),
            number=dict(font=dict(color=TEXT_C)),
        ))
        fig_gauge.update_layout(**LAYOUT,height=280,title=f"Sentiment — {sent_verdict}")
        plo(fig_gauge)

    with st.expander(f"📰 News ({len(sent_data.get('headlines',[]))} titoli) — {sent_data.get('source','N/A')} | {sent_data.get('model','N/A')}"):
        hl_all=sent_data.get("headlines",[])
        sc_all=sent_data.get("scores",[])
        if hl_all and sc_all:
            pairs=sorted(zip(sc_all,hl_all),reverse=True)
            st.markdown("**Top positivi:**")
            for s2,h in pairs[:3]: st.markdown(f"- `[{s2:+.2f}]` {h[:110]}")
            st.markdown("**Top negativi:**")
            for s2,h in pairs[-3:]: st.markdown(f"- `[{s2:+.2f}]` {h[:110]}")
        elif hl_all:
            for h in hl_all[:5]: st.markdown(f"- {h[:110]}")

# ──────────────────────────────────────────────────────────────
# TAB 12 — VERDETTO (ex tab8)
# ──────────────────────────────────────────────────────────────
with tab12:
    section("🏁","Verdetto Finale — Analisi Composita")
    st.caption("⚠️ DISCLAIMER: Solo uso educativo. Non costituisce consulenza finanziaria.")

    # ── Scoring a 8 dimensioni (da S22 notebook) ───────────────────────────
    scores_v2 = {}

    # 1. Profittabilità /20
    _s1 = 0
    _om2 = last_valid(margins.get("Operating Margin", pd.Series()))
    _roe_l2 = last_valid(roe); _roic_l2 = last_valid(roic)
    if not pd.isna(_om2):
        _s1 += 8 if _om2>0.20 else (6 if _om2>0.10 else (4 if _om2>0.05 else (2 if _om2>0 else 0)))
    if not pd.isna(_roe_l2):
        _s1 += 7 if _roe_l2>0.20 else (5 if _roe_l2>0.10 else (3 if _roe_l2>0 else 0))
    if not pd.isna(_roic_l2) and not pd.isna(wacc_calc):
        _s1 += 5 if _roic_l2>wacc_calc+0.05 else (3 if _roic_l2>wacc_calc else 1)
    scores_v2["Profittabilità (20)"] = min(_s1, 20)

    # 2. Solidità /20
    _s2 = 0
    _cr2 = last_valid(liq.get("Current Ratio", pd.Series()))
    _ic2 = last_valid(liq.get("Interest Coverage", pd.Series()))
    _nd2 = last_valid(liq.get("Net Debt/EBITDA", pd.Series()))
    _de2 = last_valid(liq.get("D/E Ratio", pd.Series()))
    if not pd.isna(_cr2): _s2 += 5 if _cr2>2 else (3 if _cr2>1 else 1)
    if not pd.isna(_ic2): _s2 += 6 if _ic2>10 else (4 if _ic2>3 else (2 if _ic2>1 else 0))
    if not pd.isna(_nd2): _s2 += 5 if _nd2<1 else (3 if _nd2<2 else (1 if _nd2<4 else 0))
    if not pd.isna(_de2): _s2 += 4 if _de2<0.5 else (2 if _de2<1.5 else (1 if _de2<3 else 0))
    scores_v2["Solidità (20)"] = min(_s2, 20)

    # 3. Crescita /15
    _s3 = 0
    _rc2 = rev_cagr_5y if not pd.isna(rev_cagr_5y) else growth.get("Revenue CAGR 3y", np.nan)
    _nc2 = growth.get("Net Income CAGR 5y", growth.get("Net Income CAGR 3y", np.nan))
    _fc2 = growth.get("FCF CAGR 5y", growth.get("FCF CAGR 3y", np.nan))
    if not pd.isna(_rc2): _s3 += 6 if _rc2>0.15 else (4 if _rc2>0.08 else (2 if _rc2>0.03 else 0))
    if not pd.isna(_nc2): _s3 += 5 if _nc2>0.15 else (3 if _nc2>0.08 else (1 if _nc2>0 else 0))
    if not pd.isna(_fc2): _s3 += 4 if _fc2>0.12 else (2 if _fc2>0.05 else 0)
    scores_v2["Crescita (15)"] = min(_s3, 15)

    # 4. Quality Earnings /15
    _s4 = 0
    if not df_quality.empty:
        try:
            _cn_avg = df_quality["CFO/NI"].replace([np.inf,-np.inf], np.nan).dropna().mean()
            _fn_avg = df_quality["FCF/NI"].replace([np.inf,-np.inf], np.nan).dropna().mean()
            _ac_avg = df_quality["Accruals"].dropna().mean()
            if not pd.isna(_cn_avg): _s4 += 6 if _cn_avg>=1.1 else (4 if _cn_avg>=0.8 else 1)
            if not pd.isna(_fn_avg): _s4 += 5 if _fn_avg>=0.8 else (3 if _fn_avg>=0.5 else 1)
            if not pd.isna(_ac_avg): _s4 += 4 if abs(_ac_avg)<0.05 else (2 if abs(_ac_avg)<0.08 else 0)
        except: _s4 = 7
    else:
        _s4 = 7
    scores_v2["Quality Earnings (15)"] = min(_s4, 15)

    # 5. Valutazione /15
    _s5 = 0
    _pe_v2 = valuation.get("P/E", np.nan)
    _eveb_v2 = valuation.get("EV/EBITDA", np.nan)
    _fv_blend = blend_price if not np.isnan(blend_price or np.nan) else np.nan
    if not pd.isna(_pe_v2) and _pe_v2>0:
        _s5 += 3 if _pe_v2<15 else (2 if _pe_v2<25 else (1 if _pe_v2<40 else 0))
    if not pd.isna(_eveb_v2) and _eveb_v2>0:
        _s5 += 3 if _eveb_v2<10 else (2 if _eveb_v2<15 else (1 if _eveb_v2<25 else 0))
    if price and not pd.isna(_fv_blend or np.nan):
        _d2 = (_fv_blend - price) / price
        _s5 += 5 if _d2>0.20 else (4 if _d2>0.10 else (3 if _d2>0 else (1 if _d2>-0.15 else 0)))
    if premium_disc is not None and not pd.isna(premium_disc):
        _s5 += max(0, int(4 * (1 - premium_disc)))
    scores_v2["Valutazione (15)"] = min(_s5, 15)

    # 6. Macro /5
    _s6 = 3  # default neutro
    if "macro_verdict" in dir() and macro_verdict == "FAVOREVOLE": _s6 = 5
    elif "macro_verdict" in dir() and macro_verdict == "SFAVOREVOLE": _s6 = 1
    scores_v2["Macro (5)"] = _s6

    # 7. Risk /5
    _s7 = (1 if risk_class == "HIGH" else 3 if risk_class == "MEDIUM" else 5 if risk_class == "LOW" else 3)
    scores_v2["Risk Profile (5)"] = _s7

    # 8. Sentiment /5
    _s8 = 3  # default neutro
    if "sent_data" in dir() and sent_data.get("scores"):
        _s8 = (5 if sentiment_avg >= 0.3 else 4 if sentiment_avg >= 0.1
               else 3 if sentiment_avg >= -0.1 else 2 if sentiment_avg >= -0.3 else 1)
    scores_v2["Sentiment (5)"] = _s8

    _total_v2 = sum(scores_v2.values())

    # Score legacy (usato da radar + flags)
    subscores = {}
    _sq2 = float(np.mean([s for s in [score_prof,score_cf] if not pd.isna(s)])) if not(pd.isna(score_prof) and pd.isna(score_cf)) else np.nan
    if not pd.isna(_sq2):           subscores["Qualità Business"]     = (_sq2, 0.20)
    if not pd.isna(score_solv):     subscores["Solidità Finanziaria"]  = (score_solv, 0.20)
    if not pd.isna(score_gr):       subscores["Crescita"]              = (score_gr, 0.15)
    _val_sc2 = float(scores_v2.get("Valutazione (15)", 0)) / 15 * 100
    subscores["Valutazione"] = (_val_sc2, 0.15)
    if not pd.isna(_roic_l2):
        subscores["ROIC vs WACC"] = (float(np.clip(50+(_roic_l2-wacc_calc)*300, 0, 100)), 0.10)
    _qe_sc2 = float(scores_v2.get("Quality Earnings (15)", 0)) / 15 * 100
    subscores["Quality Earnings"] = (_qe_sc2, 0.15)
    _risk_sc2 = float(_s7) / 5 * 100
    subscores["Risk & Macro"] = (float((_s6+_s7)/10*100), 0.05)

    final_score = float(_total_v2)  # su 100

    # Flags
    flags_crit, flags_warn = [], []
    nm_v2 = last_valid(margins.get("Net Margin",pd.Series()))
    if not pd.isna(nm_v2) and nm_v2<-0.05:
        flags_crit.append(f"Perdita netta ({nm_v2*100:.1f}% net margin)")
    fcf_s2 = df_fund.get("free_cash_flow",pd.Series()).dropna()
    if len(fcf_s2)>=2 and (fcf_s2<0).sum()/len(fcf_s2)>0.6:
        flags_crit.append("FCF negativo in >60% degli anni")
    de_v2 = last_valid(liq.get("D/E Ratio",pd.Series()))
    if not pd.isna(de_v2) and de_v2>4:  flags_crit.append(f"D/E molto elevato ({de_v2:.1f}x)")
    elif not pd.isna(de_v2) and de_v2>2: flags_warn.append(f"D/E moderato ({de_v2:.1f}x)")
    if not np.isnan(upside_mm or np.nan) and upside_mm < -0.30:
        flags_crit.append(f"Multi-model blend: {upside_mm*100:+.1f}% downside")
    elif not np.isnan(upside_mm or np.nan) and upside_mm < -0.15:
        flags_warn.append(f"Multi-model blend: {upside_mm*100:+.1f}% downside")
    if premium_disc is not None and not pd.isna(premium_disc) and premium_disc>0.40:
        flags_crit.append(f"Prezzo {premium_disc*100:.0f}% sopra fair value DCF")
    elif premium_disc is not None and not pd.isna(premium_disc) and premium_disc>0.20:
        flags_warn.append(f"Prezzo {premium_disc*100:.0f}% sopra fair value DCF")
    if risk_class == "HIGH":
        flags_warn.append(f"Risk profile HIGH — Ann.Vol {ann_vol_r*100:.0f}%  Max DD {max_dd_r*100:.0f}%")

    # Verdetto (scoring su 100)
    if not pd.isna(final_score):
        if len(flags_crit)>=2:
            verdict,v_cls,v_em = "EVITA","v-avoid","❌"
        elif final_score>=80 and not flags_crit:
            verdict,v_cls,v_em = "STRONG BUY","v-buy","🚀"
        elif final_score>=65 and not flags_crit:
            verdict,v_cls,v_em = "COMPRA","v-buy","✅"
        elif final_score>=65:
            verdict,v_cls,v_em = "COMPRA CON CAUTELA","v-buy","⚠️"
        elif final_score>=50:
            verdict,v_cls,v_em = "ATTENDI","v-wait","⏳"
        elif final_score>=35:
            verdict,v_cls,v_em = "ATTENDI / EVITA","v-wait","⚠️"
        else:
            verdict,v_cls,v_em = "EVITA","v-avoid","❌"
    else:
        verdict,v_cls,v_em = "DATI INSUFFICIENTI","v-neutral","❓"

    fv_values_t = {k:v for k,v in fair_values.items() if v and not pd.isna(v) and v>0}
    fv_med_t    = (blend_price if not np.isnan(blend_price or np.nan) and (blend_price or 0) > 0
                   else float(np.median(list(fv_values_t.values()))) if fv_values_t else None)
    entry_t     = fv_med_t * 0.80 if fv_med_t else None

    # Score 8D display
    section("📊","Scoring 8 Dimensioni (S22)")
    _dims_disp = list(scores_v2.keys())
    _maxs_disp = [int(k.split("(")[1].replace(")","")) for k in _dims_disp]
    for _dim, _mx in zip(_dims_disp, _maxs_disp):
        _sc_d = scores_v2[_dim]; _pct_d = _sc_d/_mx*100
        _c_d  = GREEN if _pct_d >= 70 else ORANGE if _pct_d >= 50 else RED
        st.markdown(
            f"<div class='sb-row'>"
            f"<span class='sb-label'>{_dim}</span>"
            f"<div class='sb-track'><div class='sb-fill' style='width:{_pct_d:.0f}%;background:{_c_d}'></div></div>"
            f"<span class='sb-num' style='color:{_c_d}'>{_sc_d}/{_mx}</span>"
            f"</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:1.1rem;font-weight:700;margin:12px 0 4px 0'>"
                f"Totale: <span style='color:{GREEN if _total_v2>=65 else ORANGE if _total_v2>=50 else RED}'>{_total_v2}/100</span></div>",
                unsafe_allow_html=True)
    st.markdown("")

    st.markdown(f"""<div class="{v_cls}">
      <h2 style="margin:0">{v_em} {verdict}</h2>
      <p style="margin:8px 0 0 0;color:#8b949e">
        Score: <strong>{final_score:.0f}/100</strong>
        &nbsp;|&nbsp; Fair Value (blend): <strong>{"$"+f"{fv_med_t:.2f}" if fv_med_t else "N/A"}</strong>
        &nbsp;|&nbsp; Prezzo: <strong>{"$"+f"{price:.2f}" if price else "N/A"}</strong>
        &nbsp;|&nbsp; Upside: <strong style="color:{'#3fb950' if (upside_mm or 0)>0 else '#f78166'}">{"N/A" if np.isnan(upside_mm or np.nan) else f"{upside_mm*100:+.1f}%"}</strong>
      </p>
      {"<p style='margin:4px 0 0 0'>Entry target (MOS 20%): <strong>$"+f"{entry_t:.2f}"+"</strong></p>" if entry_t else ""}
    </div>""", unsafe_allow_html=True)
    st.markdown("")

    # Score breakdown
    if subscores:
        section("📊","Score Breakdown")
        for dim,(sc2,w) in subscores.items():
            col2 = GREEN if sc2>=70 else ORANGE if sc2>=50 else RED
            st.markdown(
                f"<div class='sb-row'>"
                f"<span class='sb-label'>{dim}</span>"
                f"<div class='sb-track'>"
                f"<div class='sb-fill' style='width:{sc2}%;background:{col2}'></div></div>"
                f"<span class='sb-num' style='color:{col2}'>{sc2:.0f}/100</span>"
                f"<span class='sb-w'>peso {w*100:.0f}%</span>"
                f"</div>", unsafe_allow_html=True)

    # Radar finale
    if len(subscores)>=3:
        st.markdown("")
        labels_r = list(subscores.keys())
        vals_r   = [sc2 for sc2,_ in subscores.values()]
        N        = len(labels_r)
        fig_rf   = go.Figure()
        fig_rf.add_trace(go.Scatterpolar(
            r=vals_r+[vals_r[0]],theta=labels_r+[labels_r[0]],
            name=ticker,fill="toself",fillcolor="rgba(88,166,255,.15)",
            line=dict(color=ACCENT,width=3),marker=dict(size=8)))
        for zv,zn,zc in [(80,"Eccellente","rgba(63,185,80,.07)"),
                          (60,"Buono","rgba(255,166,87,.07)"),
                          (40,"Sufficiente","rgba(247,129,102,.07)")]:
            fig_rf.add_trace(go.Scatterpolar(
                r=[zv]*N+[zv],theta=labels_r+[labels_r[0]],
                fill="toself",fillcolor=zc,line=dict(color="rgba(0,0,0,0)"),
                showlegend=False,name=zn))
        fig_rf.update_layout(**LAYOUT,
            polar=dict(bgcolor=AX_BG,
                       radialaxis=dict(visible=True,range=[0,100],gridcolor=GRID_C,
                                       tickfont=dict(color=MUTED,size=9)),
                       angularaxis=dict(gridcolor=GRID_C,tickfont=dict(color=TEXT_C,size=10))),
            title=f"{company_name} — Score {final_score:.0f}/100 | {verdict}" if not pd.isna(final_score) else company_name,
            height=500)
        plo(fig_rf)

    # Flags
    if flags_crit or flags_warn:
        section("⚠️","Rischi & Segnali")
        for f in flags_crit:
            st.markdown(f'<div class="fcrit">🔴 <strong>Critico:</strong> {f}</div>',unsafe_allow_html=True)
        for w_f in flags_warn:
            st.markdown(f'<div class="fwarn">🟡 <strong>Attenzione:</strong> {w_f}</div>',unsafe_allow_html=True)

    # Macro & sentiment summary
    st.markdown("")
    ms1,ms2 = st.columns(2)
    mac_c = GREEN if macro_verdict=="FAVOREVOLE" else RED if macro_verdict=="SFAVOREVOLE" else ORANGE
    sv_c  = GREEN if sentiment_avg>=0.1 else RED if sentiment_avg<=-0.1 else ORANGE
    sv_t  = sent_verdict if sent_data.get("scores") else "N/A"
    with ms1: st.markdown(f"🌍 **Macro**: <span style='color:{mac_c}'>{macro_verdict}</span>",unsafe_allow_html=True)
    with ms2: st.markdown(f"📰 **Sentiment**: <span style='color:{sv_c}'>{sv_t}</span>",unsafe_allow_html=True)

    # Riepilogo operativo
    st.markdown("---")
    st.markdown("### 💼 Riepilogo Operativo")
    if verdict in ("COMPRA","COMPRA CON CAUTELA"):
        if entry_t and price:
            if price<=entry_t*1.03:
                st.success(f"✅ Prezzo attuale (${price:.2f}) vicino/sotto il target. Zona acquisto: ${entry_t*0.97:.2f}–${entry_t*1.03:.2f}")
            else:
                gap=(price/entry_t-1)*100
                st.info(f"⏳ Prezzo è {gap:.1f}% sopra il target (${entry_t:.2f}). Attendi pullback.")
        else:
            st.info("Fondamentali positivi. Verifica il prezzo di entrata manualmente.")
    elif verdict in ("ATTENDI","ATTENDI / EVITA"):
        msg = f"Attendi miglioramento o pullback verso ${entry_t:.2f}." if entry_t else "Attendi miglioramento dei fondamentali."
        st.warning(f"⏳ {msg}")
    else:
        st.error("❌ Business debole o valutazione eccessiva. Considera alternative.")

    # Export report
    st.markdown("")
    section("📥","Export Report")
    report_lines = [
        f"{'='*70}",
        f"  ANALISI FONDAMENTALE — {company_name} ({ticker})",
        f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Fonte: {data_source}",
        f"{'='*70}",
        "",
        f"VERDETTO: {v_em} {verdict}",
        f"Score: {final_score:.0f}/100",
        f"Fair Value (blend): {'$'+f'{fv_med_t:.2f}' if fv_med_t else 'N/A'}",
        f"Prezzo attuale: {'$'+f'{price:.2f}' if price else 'N/A'}",
        f"Upside/Downside: {upside_mm*100:+.1f}%" if not np.isnan(upside_mm or np.nan) else "Upside: N/A",
        f"Entry target (MOS 20%): {'$'+f'{entry_t:.2f}' if entry_t else 'N/A'}",
        "",
        f"{'─'*70}",
        "SCORING 8 DIMENSIONI",
        f"{'─'*70}",
    ]
    for _dim2, _sc2d in scores_v2.items():
        _mx2 = int(_dim2.split("(")[1].replace(")",""))
        _b2 = int(_sc2d/_mx2*20)
        report_lines.append(f"  {_dim2:<28} {_sc2d:>2}/{_mx2}  [{'#'*_b2}{'.'*(20-_b2)}]")
    report_lines += [f"  {'TOTALE':<28} {_total_v2:>3}/100", ""]

    report_lines += [f"{'─'*70}", "1. OVERVIEW & MERCATO", f"{'─'*70}"]
    if "revenue"          in df_fund.columns: report_lines.append(f"  Revenue:            {fmt_m(last_valid(df_fund['revenue']))}")
    if "net_income"       in df_fund.columns: report_lines.append(f"  Net Income:         {fmt_m(last_valid(df_fund['net_income']))}")
    if "free_cash_flow"   in df_fund.columns: report_lines.append(f"  Free Cash Flow:     {fmt_m(last_valid(df_fund['free_cash_flow']))}")
    report_lines.append(f"  Market Cap:         {fmt_m(market_cap)}")
    report_lines.append(f"  Settore:            {sector} | {industry}")
    report_lines.append(f"  Fonte dati:         {data_source}")

    report_lines += ["", f"{'─'*70}", "2. PROFITTABILITÀ", f"{'─'*70}"]
    for _mg, _ms in margins.items():
        report_lines.append(f"  {_mg:<22} {fmt_pct(last_valid(_ms))}")
    _roic_l3 = last_valid(roic)
    report_lines.append(f"  {'ROIC':<22} {fmt_pct(_roic_l3)}")
    report_lines.append(f"  {'WACC':<22} {wacc_calc*100:.2f}%")
    report_lines.append(f"  {'Spread ROIC-WACC':<22} {(_roic_l3-wacc_calc)*100:+.2f}%" if not pd.isna(_roic_l3) else "  Spread ROIC-WACC: N/A")

    report_lines += ["", f"{'─'*70}", "3. BETA & WACC DETTAGLIO", f"{'─'*70}"]
    report_lines.append(f"  Beta OLS raw:       {beta_ols:.3f}")
    report_lines.append(f"  Beta Blume adj:     {beta_blume:.3f}")
    report_lines.append(f"  Ke (cost equity):   {ke_calc*100:.2f}%")
    report_lines.append(f"  Kd after-tax:       {kd_calc*100:.2f}%")
    report_lines.append(f"  E/V:                {eq_w_wacc*100:.1f}%  D/V: {debt_w_wacc*100:.1f}%")
    report_lines.append(f"  WACC:               {wacc_calc*100:.2f}%")

    report_lines += ["", f"{'─'*70}", "4. SOLIDITÀ FINANZIARIA", f"{'─'*70}"]
    for _lk, _ls in liq.items():
        report_lines.append(f"  {_lk:<22} {fmt_x(last_valid(_ls))}")

    report_lines += ["", f"{'─'*70}", "5. CRESCITA", f"{'─'*70}"]
    for _gk, _gv in list(growth.items())[:12]:
        if not pd.isna(_gv): report_lines.append(f"  {_gk:<28} {_gv*100:.1f}%")

    report_lines += ["", f"{'─'*70}", "6. VALUTAZIONE MULTIPLI", f"{'─'*70}"]
    for _vk, _vv in valuation.items():
        if not pd.isna(_vv): report_lines.append(f"  {_vk:<22} {_vv:.1f}x")

    report_lines += ["", f"{'─'*70}", "7. MULTI-MODEL VALUATION", f"{'─'*70}"]
    for _mn7, (_mv7, _mw7) in _norm_mv.items():
        _up7 = ((_mv7-price)/price) if price and not np.isnan(_mv7) else np.nan
        report_lines.append(f"  {_mn7:<22} ${_mv7:.2f}  peso {_mw7*100:.0f}%  upside {'N/A' if np.isnan(_up7) else f'{_up7:+.1%}'}")
    report_lines.append(f"  {'BLEND FINALE':<22} ${blend_price:.2f}" if not np.isnan(blend_price or np.nan) else "  BLEND: N/A")
    report_lines.append(f"  Confidenza modelli: {mm_confidence}  (CV {iv_cv:.0f}%)" if not np.isnan(iv_cv or np.nan) else "")

    report_lines += ["", f"{'─'*70}", "8. SCENARIO ANALYSIS", f"{'─'*70}"]
    for _sn5, _sv5 in scenario_results.items():
        _fv5 = _sv5.get("fair_value", np.nan)
        _up5 = ((_fv5-price)/price) if price and not np.isnan(_fv5 or np.nan) else np.nan
        report_lines.append(f"  {_sn5:<12} {'$'+f'{_fv5:.2f}' if not np.isnan(_fv5 or np.nan) else 'N/D'}  {'upside '+f'{_up5:+.1%}' if not np.isnan(_up5 or np.nan) else 'N/A'}")
    if not np.isnan(implied_g or np.nan):
        report_lines.append(f"  Crescita implicita nel prezzo: {implied_g*100:.1f}%  (storica: {_rev_g_base*100:.1f}%)")

    report_lines += ["", f"{'─'*70}", "9. RISK METRICS", f"{'─'*70}"]
    for _rk3, _rv3 in risk_metrics.items():
        _fmt3 = f"{_rv3:.2f}" if "Ratio" in _rk3 else fmt_pct(_rv3)
        report_lines.append(f"  {_rk3:<22} {_fmt3}")
    report_lines.append(f"  Risk Class:            {risk_class}")

    report_lines += ["", f"{'─'*70}", "10. QUALITY OF EARNINGS", f"{'─'*70}"]
    if not df_quality.empty:
        report_lines.append(df_quality.to_string())

    if flags_crit or flags_warn:
        report_lines += ["", f"{'─'*70}", "SEGNALI & RISCHI", f"{'─'*70}"]
        for _f in flags_crit: report_lines.append(f"  🔴 CRITICO: {_f}")
        for _w in flags_warn:  report_lines.append(f"  🟡 ATTENZIONE: {_w}")

    report_lines += [
        "", f"{'='*70}",
        "⚠️  DISCLAIMER: Solo uso educativo/informativo.",
        "    Non costituisce consulenza finanziaria o raccomandazione di investimento.",
        f"{'='*70}",
    ]
    report_txt = "\n".join(report_lines)
    st.download_button("📄 Scarica Report Testo",
                       data=report_txt,
                       file_name=f"{ticker}_analisi_{datetime.now().strftime('%Y%m%d')}.txt",
                       mime="text/plain", use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style="text-align:center;color:{MUTED};font-size:.78rem;padding:10px 0">
  📊 Analisi Fondamentale v3 &nbsp;|&nbsp;
  SEC EDGAR · FMP · FRED · NewsAPI &nbsp;|&nbsp;
  Powered by Streamlit + Plotly<br>
  ⚠️ Solo uso educativo/informativo. Non costituisce consulenza finanziaria.
</div>""", unsafe_allow_html=True)
