"""
European number format normalisation utilities.

European filings use both:
  • Continental format: 1.234.567,89  (period = thousands sep, comma = decimal)
  • Anglo-Saxon format: 1,234,567.89  (comma = thousands sep, period = decimal)

Also handles scale suffixes (thousands, millions, billions) and the XBRL
`decimals` attribute (negative values mean scale, e.g. decimals=-6 means value
is already in millions of the reporting currency).
"""

from __future__ import annotations
import re


# Compiled patterns for performance
_RE_ONLY_DIGITS = re.compile(r"^-?\d+$")
_RE_EU_FORMAT = re.compile(r"^-?[\d\.]+,\d+$")      # 1.234,56
_RE_US_FORMAT = re.compile(r"^-?[\d,]+\.\d+$")       # 1,234.56


def clean_numeric(
    raw: str | float | int | None,
    decimals: int | None = None,
) -> float | None:
    """
    Normalise a raw number string from an ESEF/iXBRL filing.

    Parameters
    ----------
    raw:
        Raw value as extracted from the XBRL fact (string or numeric).
    decimals:
        The XBRL `decimals` attribute value (integer or None).
        - Positive: number of decimal places (no scaling needed).
        - Negative: neglog10 of the unit; e.g. -6 means the value is already
          in millions, so multiply by 10^6 to get the actual value.
          Wait — actually per XBRL spec: the value IS the value and
          `decimals` indicates precision. decimals=-6 means precision to
          the nearest million (i.e. the value is expressed in millions
          implicitly). We multiply raw_value × 10^|decimals| only when
          decimals < 0 AND the value appears to already be scaled.
          NOTE: In practice, ESEF iXBRL embeds the SCALED value and marks
          it with decimals=-6 (millions) or decimals=-3 (thousands). So
          we DO multiply: actual = raw_value × 10^(-decimals) when decimals < 0.

    Returns
    -------
    float or None
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
    else:
        raw = str(raw).strip().replace("\xa0", "").replace(" ", "")
        if not raw or raw in ("-", "—", "N/A", "n/a", ""):
            return None
        # Remove parentheses → negative (common in financial tables)
        negative = False
        if raw.startswith("(") and raw.endswith(")"):
            negative = True
            raw = raw[1:-1]
        elif raw.startswith("-"):
            negative = True
            raw = raw[1:]

        raw = raw.lstrip("+")

        # Detect format
        if _RE_EU_FORMAT.match(raw):
            # Continental: remove . as thousands separator, replace , with .
            raw = raw.replace(".", "").replace(",", ".")
        elif _RE_US_FORMAT.match(raw):
            # Anglo-Saxon: remove , as thousands separator
            raw = raw.replace(",", "")
        else:
            # Last resort: strip all non-numeric except . and -
            raw = re.sub(r"[^\d.\-]", "", raw)

        try:
            val = float(raw)
        except ValueError:
            return None

        if negative:
            val = -val

    if decimals is not None and decimals < 0:
        # Scale the value: decimals=-6 → multiply by 10^6
        val = val * (10 ** (-decimals))

    return val


def apply_scale(value: float | None, scale: str | None) -> float | None:
    """
    Apply a textual scale modifier to a value.

    Parameters
    ----------
    value : already cleaned float
    scale : XBRL `scale` attribute string, e.g. "3" (thousands), "6" (millions)

    Returns
    -------
    Scaled float or None
    """
    if value is None or scale is None:
        return value
    try:
        power = int(scale)
        return value * (10 ** power)
    except (ValueError, TypeError):
        _scale_map = {
            "thousand": 3,
            "thousands": 3,
            "million": 6,
            "millions": 6,
            "billion": 9,
            "billions": 9,
        }
        power = _scale_map.get(str(scale).lower().strip())
        if power is not None:
            return value * (10 ** power)
        return value
