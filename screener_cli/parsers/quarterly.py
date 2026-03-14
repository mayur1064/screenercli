"""Parser for Quarterly Results section."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import FinancialTable
from .utils import parse_section_table


def parse(soup: BeautifulSoup) -> FinancialTable | None:
    """
    Parse the Quarterly Results table (section id: ``quarters``).

    Returns a ``FinancialTable`` with ``period_type="quarterly"``, or
    ``None`` if the section is absent.
    """
    return parse_section_table(
        soup=soup,
        section_id="quarters",
        section_name="Quarterly Results",
        period_type="quarterly",
    )
