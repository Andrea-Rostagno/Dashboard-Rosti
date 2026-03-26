"""
iXBRL (Inline XBRL) parser for ESEF annual report documents.

ESEF documents are XHTML files with embedded XBRL tags such as::

    <ix:nonFraction contextRef="ctx_2024" name="ifrs-full:Revenue"
                    unitRef="EUR" decimals="-6">20600</ix:nonFraction>

The parser:
1. Locates all ix:nonFraction and ix:nonNumeric elements.
2. Resolves contextRef → period dates.
3. Resolves unitRef → currency.
4. Applies the decimals/scale attribute to recover the true monetary value.
5. Maps IFRS tag names (including company-specific namespaces) to field names.
6. Returns a list of fact dicts and a helper to aggregate them to annual figures.
"""

from __future__ import annotations
import io
import logging
import re
import zipfile
from datetime import date, datetime
from typing import Any

from eu_data.parsers.ifrs_tags import IFRS_TO_FIELD, IFRS_SHORT_NAMES
from eu_data.parsers.numeric_cleaner import clean_numeric, apply_scale
from eu_data.utils.logger import get_logger

logger = get_logger(__name__)

# BeautifulSoup with lxml or html.parser fallback
try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not installed — iXBRL parsing unavailable")


class ParseError(Exception):
    """Raised when an iXBRL document cannot be parsed."""


def _parse_date(s: str | None) -> date | None:
    """Parse an ISO date string to a date object, returning None on failure."""
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


class IXBRLParser:
    """
    Parse iXBRL/ESEF documents from bytes, file paths, or URLs.

    Example::

        parser = IXBRLParser()
        facts = parser.parse_from_bytes(xhtml_bytes, filename="report.xhtml")
        annual = parser.to_annual_financials(facts, year=2023)
    """

    def __init__(self, http_client: Any = None) -> None:
        """
        Parameters
        ----------
        http_client : RobustHTTPClient instance (optional).
            Required only for parse_from_url.
        """
        self._http = http_client

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def parse_from_bytes(
        self, content: bytes, filename: str = ""
    ) -> list[dict]:
        """
        Parse an iXBRL document from raw bytes.

        Handles plain XHTML and ZIP archives containing XHTML/HTML files.

        Returns
        -------
        list of dicts with keys:
            tag, field, value, period_start, period_end, period_instant,
            currency, decimals, context_id, negated, raw_value
        """
        if not _BS4_AVAILABLE:
            raise ParseError("beautifulsoup4 is required for iXBRL parsing")

        # If ZIP — find the main iXBRL document inside
        if content[:4] == b"PK\x03\x04" or filename.lower().endswith(".zip"):
            content = self._extract_from_zip(content)
            if content is None:
                raise ParseError("No iXBRL document found inside ZIP")

        try:
            text = content.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ParseError(f"Could not decode content: {exc}") from exc

        return self._parse_html(text)

    def parse_from_url(self, url: str) -> list[dict]:
        """
        Download an iXBRL document from `url` and parse it.

        Requires http_client to have been passed to __init__.
        """
        if self._http is None:
            raise ParseError("http_client required for parse_from_url")
        logger.info("Downloading iXBRL from %s", url)
        raw = self._http.download_binary(url)
        filename = url.split("/")[-1].split("?")[0]
        return self.parse_from_bytes(raw, filename=filename)

    def to_annual_financials(
        self,
        facts: list[dict],
        year: int | None = None,
    ) -> dict[str, float | None]:
        """
        Aggregate a flat list of facts into a dict of {field_name: value}
        for the most recent annual period (or the specified year).

        Annual period = period_end.month in (11, 12, 1) and duration ≥ 300 days,
        OR (period_end - period_start) ≥ 300 days.

        Strategy: for each field, prefer the annual period closest to `year`
        (or to the latest available period if year=None). Picks the fact with
        the longest duration when there are duplicates.
        """
        if not facts:
            return {}

        # Determine target year
        if year is None:
            ends = [
                f["period_end"]
                for f in facts
                if f.get("period_end") and isinstance(f["period_end"], date)
            ]
            if ends:
                year = max(ends).year
            else:
                return {}

        # Filter to annual-length periods ending in target year (±1)
        annual_facts = []
        for f in facts:
            pe: date | None = f.get("period_end")
            ps: date | None = f.get("period_start")
            pi: date | None = f.get("period_instant")
            ref_date = pe or pi
            if ref_date is None:
                continue
            if abs(ref_date.year - year) > 1:
                continue
            # Determine duration
            if pe and ps:
                dur = (pe - ps).days
            elif pi:
                dur = 365   # instant facts (balance sheet)
            else:
                dur = 0
            if dur >= 300 or pi:  # balance sheet instants are always ok
                annual_facts.append((f, dur))

        result: dict[str, tuple[float, int, date]] = {}  # field → (value, dur, period_end)
        for f, dur in annual_facts:
            field = f.get("field")
            value = f.get("value")
            if not field or value is None:
                continue
            ref_date = f.get("period_end") or f.get("period_instant") or date.min
            if isinstance(ref_date, str):
                ref_date = _parse_date(ref_date) or date.min
            existing = result.get(field)
            if existing is None:
                result[field] = (value, dur, ref_date)
            else:
                _, ex_dur, ex_date = existing
                # Prefer closer year, then longer duration
                if abs(ref_date.year - year) < abs(ex_date.year - year):
                    result[field] = (value, dur, ref_date)
                elif abs(ref_date.year - year) == abs(ex_date.year - year) and dur > ex_dur:
                    result[field] = (value, dur, ref_date)

        return {field: v for field, (v, _, _) in result.items()}

    # ------------------------------------------------------------------ #
    # Internal parsing
    # ------------------------------------------------------------------ #

    def _extract_from_zip(self, content: bytes) -> bytes | None:
        """Extract the primary iXBRL XHTML document from a ZIP archive."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile:
            return None
        names = zf.namelist()
        logger.debug("ZIP contents: %s", names)

        # Preference order: .xhtml > .html > .htm
        for ext in (".xhtml", ".html", ".htm"):
            candidates = [n for n in names if n.lower().endswith(ext)]
            # Exclude manifest and taxonomy files
            candidates = [
                n for n in candidates
                if not any(
                    skip in n.lower()
                    for skip in ["_manifest", "taxonom", "label", "schema", ".xsd"]
                )
            ]
            if candidates:
                # Prefer the largest file (likely the full report)
                candidates.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
                logger.info("Extracting %s from ZIP", candidates[0])
                return zf.read(candidates[0])
        return None

    def _parse_html(self, text: str) -> list[dict]:
        """Parse an XHTML string and extract all iXBRL facts."""
        # Try lxml first for speed; fall back to html.parser
        for parser_name in ("lxml", "html.parser"):
            try:
                soup = BeautifulSoup(text, parser_name)
                break
            except Exception:
                continue
        else:
            raise ParseError("Could not parse HTML with lxml or html.parser")

        contexts = self._extract_contexts(soup)
        units = self._extract_units(soup)
        facts = self._extract_facts(soup, contexts, units)
        logger.info(
            "iXBRL parse: %d contexts, %d units, %d facts",
            len(contexts), len(units), len(facts),
        )
        return facts

    def extract_contexts(self, soup: "BeautifulSoup") -> dict:
        """
        Parse <xbrli:context> or <context> elements.

        Returns
        -------
        dict mapping context_id → {period_start, period_end, period_instant}
        """
        return self._extract_contexts(soup)

    def extract_units(self, soup: "BeautifulSoup") -> dict:
        """
        Parse <xbrli:unit> elements.

        Returns
        -------
        dict mapping unit_id → currency_code (e.g. "EUR")
        """
        return self._extract_units(soup)

    def extract_facts(
        self,
        soup: "BeautifulSoup",
        contexts: dict,
        units: dict,
    ) -> list[dict]:
        """Find all ix:nonFraction / ix:nonNumeric facts with IFRS tags."""
        return self._extract_facts(soup, contexts, units)

    def _extract_contexts(self, soup: "BeautifulSoup") -> dict:
        contexts: dict = {}
        # XBRL context elements appear with various namespace prefixes
        for tag_name in (
            "xbrli:context", "xbrldi:context", "context",
            soup.new_tag("x").name,  # dummy, triggers fallback below
        ):
            elements = soup.find_all(tag_name)
            if elements:
                break
        else:
            # Broad search — any element whose local name is "context"
            elements = [
                el for el in soup.find_all(True)
                if el.name and el.name.split(":")[-1].lower() == "context"
            ]

        for ctx in elements:
            ctx_id = ctx.get("id")
            if not ctx_id:
                continue
            period = ctx.find(
                lambda t: t.name and t.name.split(":")[-1].lower() == "period"
            )
            if period is None:
                continue
            instant_el = period.find(
                lambda t: t.name and t.name.split(":")[-1].lower() == "instant"
            )
            start_el = period.find(
                lambda t: t.name and t.name.split(":")[-1].lower() == "startdate"
            )
            end_el = period.find(
                lambda t: t.name and t.name.split(":")[-1].lower() == "enddate"
            )
            contexts[ctx_id] = {
                "period_instant": _parse_date(instant_el.get_text(strip=True) if instant_el else None),
                "period_start": _parse_date(start_el.get_text(strip=True) if start_el else None),
                "period_end": _parse_date(end_el.get_text(strip=True) if end_el else None),
            }
        return contexts

    def _extract_units(self, soup: "BeautifulSoup") -> dict:
        units: dict = {}
        elements = [
            el for el in soup.find_all(True)
            if el.name and el.name.split(":")[-1].lower() == "unit"
        ]
        for unit in elements:
            unit_id = unit.get("id")
            if not unit_id:
                continue
            measure_el = unit.find(
                lambda t: t.name and t.name.split(":")[-1].lower() == "measure"
            )
            if measure_el:
                measure = measure_el.get_text(strip=True)
                # "iso4217:EUR" → "EUR"
                currency = measure.split(":")[-1].upper()
                units[unit_id] = currency
        return units

    def _resolve_tag(self, name: str) -> str | None:
        """
        Resolve an XBRL tag name to a NormalizedFinancials field name.

        Handles:
        - Full qualified name: "ifrs-full:Revenue" → "revenue"
        - Short name: "Revenue" → "revenue"
        - Company namespace: "thales-2024:Revenue" → "revenue" (via short name)
        """
        if not name:
            return None
        # 1) Direct match
        field = IFRS_TO_FIELD.get(name)
        if field:
            return field
        # 2) Short name match (strip namespace prefix)
        short = name.split(":")[-1]
        field = IFRS_SHORT_NAMES.get(short)
        if field:
            return field
        # 3) Case-insensitive short name match
        short_lower = short.lower()
        for key, val in IFRS_SHORT_NAMES.items():
            if key.lower() == short_lower:
                return val
        return None

    def _extract_facts(
        self,
        soup: "BeautifulSoup",
        contexts: dict,
        units: dict,
    ) -> list[dict]:
        facts: list[dict] = []

        # Find all ix:nonFraction, ix:nonNumeric elements regardless of namespace prefix
        ix_elements = []
        for el in soup.find_all(True):
            local = el.name.split(":")[-1].lower() if el.name else ""
            if local in ("nonfraction", "nonnumeric", "fraction"):
                ix_elements.append(el)

        # Also search by explicit tag names as a safety net
        for tag_name in (
            "ix:nonfraction", "ix:nonnumeric",
            "ix:nonFraction", "ix:nonNumeric",
        ):
            for el in soup.find_all(tag_name):
                if el not in ix_elements:
                    ix_elements.append(el)

        logger.debug("Found %d ix elements", len(ix_elements))

        for el in ix_elements:
            name = el.get("name", "")
            if not name:
                continue
            field = self._resolve_tag(name)
            if not field:
                continue

            ctx_ref = el.get("contextref") or el.get("contextRef", "")
            unit_ref = el.get("unitref") or el.get("unitRef", "")
            decimals_attr = el.get("decimals")
            scale_attr = el.get("scale")
            negated = el.get("sign", "") == "-" or (
                el.get("negated", "false").lower() in ("true", "1", "yes")
            )

            # Get text content (may contain formatted number)
            raw_text = el.get_text(strip=True)
            # Some documents use ix:exclude inside to hide the value
            exclude = el.find(
                lambda t: t.name and t.name.split(":")[-1].lower() == "exclude"
            )
            if exclude:
                for ex in el.find_all(
                    lambda t: t.name and t.name.split(":")[-1].lower() == "exclude"
                ):
                    ex.decompose()
                raw_text = el.get_text(strip=True)

            # Parse decimals
            decimals: int | None = None
            if decimals_attr is not None:
                try:
                    decimals = int(decimals_attr)
                except ValueError:
                    pass

            # Clean the numeric value
            value = clean_numeric(raw_text, decimals=decimals)
            if value is None:
                continue

            # Apply scale attribute if present
            if scale_attr:
                value = apply_scale(value, scale_attr)
            if value is None:
                continue

            # Handle negation
            if negated:
                value = -value

            # Resolve context
            ctx = contexts.get(ctx_ref, {})
            period_start = ctx.get("period_start")
            period_end = ctx.get("period_end")
            period_instant = ctx.get("period_instant")

            # Resolve currency from unit
            currency = units.get(unit_ref, "")

            facts.append({
                "tag": name,
                "field": field,
                "value": value,
                "raw_value": raw_text,
                "period_start": period_start,
                "period_end": period_end,
                "period_instant": period_instant,
                "currency": currency,
                "decimals": decimals,
                "context_id": ctx_ref,
                "unit_id": unit_ref,
                "negated": negated,
            })

        return facts
