"""Parser for Key Ratios section (annual)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import FinancialTable
from .utils import parse_section_table

# Brief descriptions for common ratios shown on screener.in
RATIO_DESCRIPTIONS: dict[str, str] = {
    "Debtor Days": "Average number of days to collect receivables.",
    "Inventory Days": "Average number of days inventory is held.",
    "Days Payable": "Average number of days to pay suppliers.",
    "Cash Conversion Cycle": "Net days to convert investments into cash.",
    "Working Capital Days": "Days required to convert working capital into revenue.",
    "ROCE %": "Return on Capital Employed — pre-tax return on all capital.",
    "ROE %": "Return on Equity — net return for shareholders.",
    "OPM %": "Operating Profit Margin — operating income as % of revenue.",
    "NPM %": "Net Profit Margin — net income as % of revenue.",
    "Asset Turnover": "Revenue generated per unit of assets.",
}


def parse(soup: BeautifulSoup) -> FinancialTable | None:
    """
    Parse the Ratios table (section id: ``ratios``).

    Each row's ``unit`` field is set to the human-readable description of the
    ratio when available, otherwise ``None``.
    """
    table = parse_section_table(
        soup=soup,
        section_id="ratios",
        section_name="Key Ratios",
        period_type="annual",
    )
    if table is None:
        return None

    for row in table.rows:
        if row.unit is None:
            row.unit = RATIO_DESCRIPTIONS.get(row.label)

    return table
