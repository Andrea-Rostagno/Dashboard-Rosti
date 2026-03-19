# 📊 Analisi Fondamentale Pro

Dashboard professionale per l'analisi fondamentale di azioni quotate USA.

## Funzionalità

- **12 tab** di analisi: Overview, Profittabilità, Solidità & Cash Flow, Crescita, WACC & Beta, DCF & Sensitivity, Multipli & Peer, Scenario & Forward, Multi-Model Blend, Risk Engine, Macro & Sentiment, Verdetto
- **WACC automatico** calcolato con metodo OLS/Blume + ERP Damodaran
- **DCF** con sensitivity heatmap (WACC × TGR e Rev Growth × EBIT Margin)
- **Multi-model blend**: DCF (40%) + Multipli (30%) + Scenario (20%) + RIM (10%)
- **Risk Engine**: Sharpe, Sortino, Calmar, Max Drawdown, VaR 95%, CVaR 95%
- **Analisi Peer**: media, mediana, percentile rank, radar chart
- **Scoring 8 dimensioni**: Profittabilità, Solidità, Crescita, Quality of Earnings, Valutazione, Macro, Risk, Sentiment
- Dati da **SEC EDGAR**, **FMP**, **FRED**, **NewsAPI**, **yfinance**

## Deploy locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Stack

- Python 3.11+
- Streamlit · Plotly · Pandas · NumPy · SciPy
- yfinance · vaderSentiment

---
⚠️ *Solo uso educativo/informativo. Non costituisce consulenza finanziaria.*
