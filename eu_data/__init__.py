"""
eu_data — European company financial data pipeline.
Reads from official sources: ESEF/iXBRL, ESMA, GLEIF, OpenFIGI,
Companies House UK, CNMV Spain, AMF France.
No yfinance. No paid APIs.
"""

__version__ = "1.0.0"
__all__ = ["pipeline"]
