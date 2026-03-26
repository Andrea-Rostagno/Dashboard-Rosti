"""SourceRouter — maps country ISO-2 code to ordered list of data sources."""
from __future__ import annotations
from .base              import BaseSource
from .esef_xbrl         import ESEFXBRLSource
from .cnmv_spain        import CNMVSpainSource
from .companies_house   import CompaniesHouseSource
from ..utils.logger     import get_logger

logger = get_logger(__name__)

# Exported so sources/__init__.py can re-export it
COUNTRY_SOURCE_PRIORITY: dict[str, list[str]] = {
    "FR": ["ESEFXBRLSource"],
    "IT": ["ESEFXBRLSource"],
    "DE": ["ESEFXBRLSource"],
    "ES": ["ESEFXBRLSource", "CNMVSpainSource"],
    "NL": ["ESEFXBRLSource"],
    "BE": ["ESEFXBRLSource"],
    "PT": ["ESEFXBRLSource"],
    "AT": ["ESEFXBRLSource"],
    "FI": ["ESEFXBRLSource"],
    "SE": ["ESEFXBRLSource"],
    "DK": ["ESEFXBRLSource"],
    "NO": ["ESEFXBRLSource"],
    "CH": ["ESEFXBRLSource"],
    "PL": ["ESEFXBRLSource"],
    "IE": ["ESEFXBRLSource"],
    "GB": ["CompaniesHouseSource", "ESEFXBRLSource"],
    "DEFAULT": ["ESEFXBRLSource"],
}

_SOURCE_CLASSES: dict[str, type] = {
    "ESEFXBRLSource":       ESEFXBRLSource,
    "CNMVSpainSource":      CNMVSpainSource,
    "CompaniesHouseSource": CompaniesHouseSource,
}


class SourceRouter:
    def __init__(self, companies_house_api_key: str | None = None):
        self._ch_key = companies_house_api_key
        self._cache: dict[str, list[BaseSource]] = {}

    def get_sources(self, country: str | None) -> list[BaseSource]:
        key = (country or "").upper()
        if key in self._cache:
            return self._cache[key]
        names = COUNTRY_SOURCE_PRIORITY.get(key, COUNTRY_SOURCE_PRIORITY["DEFAULT"])
        sources: list[BaseSource] = []
        for name in names:
            cls = _SOURCE_CLASSES.get(name)
            if cls is None:
                continue
            if name == "CompaniesHouseSource":
                sources.append(cls(api_key=self._ch_key))
            else:
                sources.append(cls())
        self._cache[key] = sources
        logger.info("Country %s -> sources: %s", key, [s.SOURCE_NAME for s in sources])
        return sources
