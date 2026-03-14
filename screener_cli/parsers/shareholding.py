"""Parser for Shareholding Pattern section (quarterly)."""

from __future__ import annotations

import sys

from bs4 import BeautifulSoup, Tag

from ..models import RowData, ShareholdingTable
from .utils import _clean_value

SECTION_ID = "shareholding"

_HOLDER_CATEGORIES = {
    "promoters": "Promoters",
    "promoter": "Promoters",
    "fii": "FIIs",
    "foreign": "FIIs",
    "dii": "DIIs",
    "domestic": "DIIs",
    "mutual fund": "DIIs",
    "government": "Government",
    "public": "Public",
    "others": "Public",
}


def _normalise_holder(label: str) -> str:
    ll = label.lower()
    for keyword, category in _HOLDER_CATEGORIES.items():
        if keyword in ll:
            return category
    return label  # keep as-is if unknown


def parse(soup: BeautifulSoup) -> ShareholdingTable | None:
    """
    Parse the Shareholding Pattern table (section id: ``shareholding``).

    Returns a ``ShareholdingTable`` with:
    - ``headers`` — quarter labels
    - ``rows`` — % holding per stakeholder group over time
    - ``latest`` — dict of the most recent quarter's percentages
    """
    section: Tag | None = soup.find("section", id=SECTION_ID)  # type: ignore[assignment]
    if section is None:
        print(f"[warning] Section '{SECTION_ID}' not found on this page.", file=sys.stderr)
        return None

    table: Tag | None = section.find("table")  # type: ignore[assignment]
    if table is None:
        print(f"[warning] No table found in section '{SECTION_ID}'.", file=sys.stderr)
        return None

    # Headers
    headers: list[str] = []
    thead = table.find("thead")
    if thead:
        for th in thead.find_all("th")[1:]:
            headers.append(th.get_text(strip=True))

    # Rows
    rows: list[RowData] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        label = cells[0].get_text(strip=True)
        if not label:
            continue
        raw_values = [c.get_text(strip=True) for c in cells[1:]]
        values = [_clean_value(v) for v in raw_values]
        normalised_label = _normalise_holder(label)
        rows.append(RowData(label=normalised_label, values=values, unit="%"))

    # Latest quarter summary (last column)
    latest: dict[str, float | None] = {}
    for row in rows:
        if row.values:
            latest[row.label] = row.values[-1]

    return ShareholdingTable(
        period_type="quarterly",
        headers=headers,
        rows=rows,
        latest=latest,
    )
