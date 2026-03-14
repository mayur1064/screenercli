"""Parser for Cash Flow section (annual)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import FinancialTable
from .utils import parse_section_table

# Keywords used to tag each cash-flow row's category
_CATEGORY_MAP = {
    "operating": "Operating",
    "investing": "Investing",
    "financing": "Financing",
    "net cash": "Net",
    "closing cash": "Net",
    "opening cash": "Net",
}


def parse(soup: BeautifulSoup) -> FinancialTable | None:
    """
    Parse the Cash Flow table (section id: ``cash-flow``).

    Row ``unit`` fields are tagged as ``"Operating"``, ``"Investing"``,
    ``"Financing"``, or ``"Net"``.
    """
    table = parse_section_table(
        soup=soup,
        section_id="cash-flow",
        section_name="Cash Flow",
        period_type="annual",
    )
    if table is None:
        return None

    current_category = "Operating"
    for row in table.rows:
        label_lower = row.label.lower()
        for keyword, category in _CATEGORY_MAP.items():
            if keyword in label_lower:
                current_category = category
                break
        if row.unit is None:
            row.unit = current_category

    return table
