"""Parser for Profit & Loss section (annual) including growth tables."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from bs4 import BeautifulSoup

from ..models import FinancialTable, GrowthTable
from .utils import extract_growth_block, parse_section_table

SECTION_ID = "profit-loss"


def parse(soup: BeautifulSoup) -> dict[str, Any] | None:
    """
    Parse the Profit & Loss table plus any embedded compounded growth tables.

    Returns a dict:
    ``{"table": FinancialTable, "growth_tables": [GrowthTable, ...]}``
    or ``None`` if the section is absent.
    """
    table = parse_section_table(
        soup=soup,
        section_id=SECTION_ID,
        section_name="Profit & Loss",
        period_type="annual",
    )
    if table is None:
        return None

    raw_growth = extract_growth_block(soup, SECTION_ID)
    growth_tables = [
        GrowthTable(
            label=g["label"],
            periods=g["periods"],
            values=g["values"],
        )
        for g in raw_growth
    ]

    return {
        "table": table,
        "growth_tables": growth_tables,
    }
