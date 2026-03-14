"""Generic HTML table parser utility shared by all section parsers."""

from __future__ import annotations

import re
import sys
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..models import FinancialTable, RowData


# ---------------------------------------------------------------------------
# Value normalisation helpers
# ---------------------------------------------------------------------------

_COMMA_RE = re.compile(r"[,\s]+")
_FOOTNOTE_MARKER_RE = re.compile(r"[+*†‡§]")


def _clean_value(raw: str) -> float | None:
    """
    Convert a cell text such as ``"1,38,761"`` or ``"16%"`` or ``"--"``
    to a Python float (or ``None`` for empty / non-numeric cells).
    """
    text = raw.strip()
    if not text or text in {"-", "--", "N/A", "na", "NA"}:
        return None

    # Strip footnote markers (e.g. "1,234+")
    text = _FOOTNOTE_MARKER_RE.sub("", text)

    # Remove commas
    text = _COMMA_RE.sub("", text)

    # Handle percentage values — keep the number, note the unit upstream
    text = text.rstrip("%").strip()

    try:
        return float(text)
    except ValueError:
        return None


def _detect_unit(soup_section: Tag) -> str:
    """
    Try to detect the display unit from the section heading/description,
    e.g. ``"Figures in Rs. Crores"`` → ``"Rs. Crores"``.
    """
    for tag in soup_section.find_all(["p", "span", "small"], limit=10):
        text = tag.get_text(strip=True)
        if "crore" in text.lower():
            return "Rs. Crores"
        if "lakh" in text.lower():
            return "Rs. Lakhs"
        if "%" in text and "figure" in text.lower():
            return "Percentage"
    return "Rs. Crores"  # screener.in default


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_section_table(
    soup: BeautifulSoup,
    section_id: str,
    section_name: str,
    period_type: str = "annual",
    currency: str = "INR",
) -> FinancialTable | None:
    """
    Parse a financial table from a ``<section id="section_id">`` element.

    Returns a ``FinancialTable`` dataclass, or ``None`` if the section /
    table is not found (with a stderr warning).
    """
    section: Tag | None = soup.find("section", id=section_id)  # type: ignore[assignment]
    if section is None:
        print(f"[warning] Section '{section_id}' not found on this page.", file=sys.stderr)
        return None

    table: Tag | None = section.find("table")  # type: ignore[assignment]
    if table is None:
        print(f"[warning] No table found in section '{section_id}'.", file=sys.stderr)
        return None

    unit = _detect_unit(section)
    footnotes: list[str] = []

    # --- headers (date labels) from <thead> ---
    headers: list[str] = []
    thead = table.find("thead")
    if thead:
        for th in thead.find_all("th")[1:]:  # skip the first (row-label) column
            headers.append(th.get_text(strip=True))

    # --- rows from <tbody> ---
    rows: list[RowData] = []
    tbody = table.find("tbody")
    if tbody is None:
        tbody = table  # some tables omit <tbody>

    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        label = cells[0].get_text(strip=True)
        if not label:
            continue

        # Detect footnotes embedded in label
        label_clean = _FOOTNOTE_MARKER_RE.sub("", label).strip()
        if label_clean != label:
            footnotes.append(f"Row '{label_clean}' has footnote markers.")
        label = label_clean

        # Detect whether every non-empty value in this row ends with '%'
        raw_values = [c.get_text(strip=True) for c in cells[1:]]
        row_has_pct = any(v.strip().endswith("%") for v in raw_values if v.strip())
        row_unit: str | None = "%" if row_has_pct else None

        values = [_clean_value(v) for v in raw_values]

        # Detect subtotal rows: typically bold or have class "strong"
        is_subtotal = bool(tr.find("strong") or "strong" in tr.get("class", []))

        rows.append(RowData(label=label, values=values, unit=row_unit, is_subtotal=is_subtotal))

    return FinancialTable(
        section=section_name,
        unit=unit,
        currency=currency,
        period_type=period_type,
        headers=headers,
        rows=rows,
        footnotes=footnotes,
    )


def extract_growth_block(soup: BeautifulSoup, section_id: str) -> list[dict[str, Any]]:
    """
    Extract compounded growth tables (e.g. Sales Growth, Profit Growth)
    that appear as ``<ul>`` elements within the P&L section.

    Returns a list of dicts:
    ``[{"label": "Compounded Sales Growth", "periods": [...], "values": [...]}, ...]``
    """
    section: Tag | None = soup.find("section", id=section_id)  # type: ignore[assignment]
    if section is None:
        return []

    results: list[dict[str, Any]] = []

    for sub in section.find_all("div", class_=re.compile(r"sub[-_]section|growth|cagr", re.I)):
        heading_tag = sub.find(["h3", "h4", "h5", "strong"])
        heading = heading_tag.get_text(strip=True) if heading_tag else "Growth"

        periods: list[str] = []
        values: list[str] = []

        for li in sub.find_all("li"):
            text = li.get_text(separator=" ", strip=True)
            # Typical format: "10 Years: 14%"  or  "TTM: 8%"
            if ":" in text:
                period, value = text.split(":", 1)
                periods.append(period.strip())
                values.append(value.strip())

        if periods:
            results.append({"label": heading, "periods": periods, "values": values})

    return results
